interface StatProps {
  label: string;
  value: string;
  tone?: 'default' | 'success' | 'danger';
}

export function Stat({ label, value, tone = 'default' }: StatProps) {
  return (
    <article className="stat">
      <p className="stat__label">{label}</p>
      <p className={`stat__value stat__value--${tone}`}>{value}</p>
    </article>
  );
}
