import type { PropsWithChildren } from 'react';

type BadgeTone = 'success' | 'danger' | 'neutral';

interface BadgeProps {
  tone?: BadgeTone;
}

export function Badge({ tone = 'neutral', children }: PropsWithChildren<BadgeProps>) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
