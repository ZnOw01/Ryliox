import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthStatusCard } from "./AuthStatusCard";
import { DownloadProgressCard } from "./DownloadProgressCard";
import { SearchBooksCard } from "./SearchBooksCard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  return (
    <div className="grid items-start gap-6 md:gap-8 md:grid-cols-[minmax(320px,1fr)_minmax(0,1.25fr)]">
      <div className="grid min-w-0 gap-6">
        <AuthStatusCard />
        <SearchBooksCard />
      </div>
      <div className="min-w-0">
        <DownloadProgressCard />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
