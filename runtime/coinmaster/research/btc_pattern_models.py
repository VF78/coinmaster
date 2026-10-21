"""Fixed pilot neural recipes. No pretrained trajectory generation."""
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

class Residual(nn.Module):
    def __init__(self,cin,width,dilation):
        super().__init__();self.padding=2*dilation
        self.c1=nn.Conv1d(cin,width,3,dilation=dilation);self.c2=nn.Conv1d(width,width,3,dilation=dilation)
        self.skip=nn.Conv1d(cin,width,1) if cin!=width else nn.Identity();self.drop=nn.Dropout(.1)
    def forward(self,x):
        a=self.drop(F.gelu(self.c1(F.pad(x,(self.padding,0)))))
        a=self.drop(F.gelu(self.c2(F.pad(a,(self.padding,0)))))
        return F.gelu(a+self.skip(x))

class Heads(nn.Module):
    def __init__(self,size):
        super().__init__();self.projection=nn.Linear(size+12,64);self.direction=nn.Linear(64,3);self.quantiles=nn.Linear(64,6)
    def forward(self,x,context):
        z=F.normalize(self.projection(torch.cat((x,context),dim=1)),dim=1)
        return z,self.direction(z),self.quantiles(z).reshape(-1,2,3)

class TCN(nn.Module):
    def __init__(self,branches=2):
        super().__init__();self.branches=nn.ModuleList([nn.Sequential(*[Residual(6 if k==0 else 32,32,2**k) for k in range(6)]) for _ in range(branches)]);self.heads=Heads(32*branches)
    def forward(self,x,context):
        return self.heads(torch.cat([branch(x[:,k].transpose(1,2))[:,:,-1] for k,branch in enumerate(self.branches)],dim=1),context)

class CNN(nn.Module):
    def __init__(self):
        super().__init__();layers=[];cin=3
        for cout in (32,64,128):layers.extend([nn.Conv2d(cin,cout,3,stride=2,padding=1),nn.GroupNorm(8,cout),nn.GELU()]);cin=cout
        self.encoder=nn.Sequential(*layers,nn.AdaptiveAvgPool2d(1));self.heads=Heads(128)
    def forward(self,x,context):return self.heads(self.encoder(x).flatten(1),context)

class Projection(nn.Module):
    def __init__(self,size=1024):super().__init__();self.heads=Heads(size)
    def forward(self,x,context):return self.heads(x,context)


def soft_metric(z,y,origins,label_end,scales,tau):
    """Softmax and KL only on eligible support; zero-support anchors excluded."""
    d=.5*torch.abs(y[:,None,:6]/scales-y[None,:,:6]/scales).mean(2)+.5*torch.abs(y[:,None,6:]-y[None,:,6:]).mean(2)
    mask=(origins[:,None]>=label_end[None,:])|(label_end[:,None]<=origins[None,:])
    mask.fill_diagonal_(False);eligible=mask.any(1)
    if not eligible.any():return z.sum()*0,dict(eligible_anchors=0.,eligible_pairs=0.,target_entropy=0.)
    qlog=F.log_softmax((-d/tau)[eligible].masked_fill(~mask[eligible],-torch.inf),dim=1)
    plog=F.log_softmax((z@z.T/.1)[eligible].masked_fill(~mask[eligible],-torch.inf),dim=1)
    active=mask[eligible];q=torch.exp(qlog)
    loss=torch.where(active,q*(qlog.masked_fill(~active,0)-plog.masked_fill(~active,0)),0).sum(1).mean()
    return loss,dict(eligible_anchors=float(eligible.float().mean()),eligible_pairs=float(mask.float().mean()),target_entropy=float(-(q[active]*qlog[active]).sum().detach().cpu()/eligible.sum().detach().cpu()))


def predict_loss(logits,q,d,mfe,qscale):
    valid=d>=0;dl=F.cross_entropy(logits[valid],d[valid]) if valid.any() else logits.sum()*0
    error=mfe[:,:,None]-q;levels=torch.tensor([.2,.5,.8],device=q.device)
    pin=torch.maximum(levels*error,(levels-1)*error)/qscale[None,:,None]
    return dl+pin.mean(),dl,pin.mean()


def render(raw):
    """224 RGB, fixed panels; pure NumPy, window-only log-price/volume scale."""
    image=np.empty((224,224,3),dtype='uint8');image[:]=(10,13,18)
    for panel,v in enumerate(raw):
        o,h,l,c,vol=v.T; logs=np.log(v[:,:4]);lo,hi=logs.min(),logs.max();span=max(hi-lo,1e-9);base=panel*112
        y=lambda a: int(base+4+78*(1-(np.log(float(a))-lo)/span))
        for j in range(64):
            x=int(4+j*216/64);color=(49,185,135) if c[j]>=o[j] else (230,87,98)
            image[y(h[j]):y(l[j])+1,x]=color
            image[min(y(o[j]),y(c[j])):max(y(o[j]),y(c[j]))+1,x-1:x+2]=color
            height=int(20*vol[j]/max(float(vol.max()),1e-9));image[base+108-height:base+109,x-1:x+2]=color
    return image


def save_png(path,image):
    import zlib,struct
    h,w,_=image.shape
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    payload=b''.join(b'\x00'+image[i].tobytes() for i in range(h))
    from pathlib import Path
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(payload))+chunk(b'IEND',b''))
