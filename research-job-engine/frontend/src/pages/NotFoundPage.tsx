import { Link } from "react-router";

import { EmptyState } from "../components/ui/States";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="That route doesn’t exist."
      action={
        <Link to="/" className="text-sm font-medium text-accent hover:underline">
          Back to home
        </Link>
      }
    />
  );
}
