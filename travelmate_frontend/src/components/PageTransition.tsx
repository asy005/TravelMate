import { ReactNode } from "react";

/**
 * Wraps a route's page content with the same subtle fade+rise-in used
 * elsewhere in the app (animate-fade-up), so navigating between pages
 * feels continuous instead of an abrupt hard-cut. Purely presentational --
 * no behavior/business logic here.
 */
export const PageTransition = ({ children }: { children: ReactNode }) => {
  return <div className="animate-fade-up motion-reduce:animate-none">{children}</div>;
};
