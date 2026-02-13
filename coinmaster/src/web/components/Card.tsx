import type { PropsWithChildren, ReactNode } from 'react';

interface CardProps {
  title?: string;
  actions?: ReactNode;
  className?: string;
}

export function Card({ title, actions, className = '', children }: PropsWithChildren<CardProps>) {
  return (
    <section className={["card", className].filter(Boolean).join(' ')}>
      {(title || actions) && (
        <header className="card__header">
          {title ? <h2 className="card__title">{title}</h2> : <span />}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
