export function StateBanner({
  kind = "info",
  children,
}: {
  kind?: "info" | "warn" | "error";
  children: React.ReactNode;
}) {
  const cls = kind === "info" ? "banner" : `banner ${kind}`;
  return (
    <div className={cls} role="status">
      {children}
    </div>
  );
}
