"""Single-change representation controls; original target/loss/optimizer are reused."""
import numpy as np
from torch import nn
from .btc_pattern_models import Heads

class Context(nn.Module):
    def __init__(self):
        super().__init__();self.heads=Heads(0)
    def forward(self,x,context):
        return self.heads(context.new_empty((len(context),0)),context)

class SpatialPool(nn.AdaptiveAvgPool2d):
    """Stock pooling with a differentiable CPU route for MPS nondivisible shapes."""
    def forward(self,x):
        if x.device.type=='mps':
            return super().forward(x.to('cpu')).to(x.device)
        return super().forward(x)

class CNNSpatial(nn.Module):
    def __init__(self):
        super().__init__();layers=[];cin=3
        for cout in (32,64,128):
            layers.extend([nn.Conv2d(cin,cout,3,stride=2,padding=1),nn.GroupNorm(8,cout),nn.GELU()]);cin=cout
        self.encoder=nn.Sequential(*layers,SpatialPool((2,8)));self.heads=Heads(128*2*8)
    def forward(self,x,context):
        return self.heads(self.encoder(x).flatten(1),context)

def full_descriptor(data):
    return np.concatenate((data.x.reshape(len(data.x),-1),data.c),axis=1).astype('float32')
