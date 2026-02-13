import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

export function Button({ children, className = '', variant = 'secondary', fullWidth = false, ...props }: PropsWithChildren<ButtonProps>) {
  const classes = ['btn', `btn--${variant}`, fullWidth ? 'btn--full' : '', className].filter(Boolean).join(' ');
  return (
    <button className={classes} {...props}>
      {children}
    </button>
  );
}
