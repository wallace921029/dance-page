import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { meQuery } from "@/api/auth";
import { isUnauthorized } from "@/lib/api";

/** 原本已登录、请求却返回 401：会话已过期或账号被停用，回到登录页 */
function handleSessionExpired(error: unknown) {
  if (!isUnauthorized(error) || !queryClient.getQueryData(meQuery.queryKey)) return;
  queryClient.clear();
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`/login?next=${next}`);
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleSessionExpired }),
  mutationCache: new MutationCache({ onError: handleSessionExpired }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // 401 不重试
      retry: (count, error) => !isUnauthorized(error) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});
