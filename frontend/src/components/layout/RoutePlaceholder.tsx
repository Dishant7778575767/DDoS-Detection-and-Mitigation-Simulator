type RoutePlaceholderProps = {
  title: string;
  description: string;
};

export function RoutePlaceholder({
  title,
  description,
}: RoutePlaceholderProps) {
  return (
    <section aria-labelledby="page-title" className="page-content mx-auto">
      <p className="eyebrow">Phase 1 foundation</p>
      <h1 id="page-title">{title}</h1>
      <p className="page-description">{description}</p>
      <div className="notice" role="status">
        <strong>Interface scaffold only.</strong>
        <span>
          This page does not yet display operational data or provide controls.
          Backend integration is planned for a later phase.
        </span>
      </div>
    </section>
  );
}
