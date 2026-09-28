import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, isUnauthorized } from "@/lib/api";
import type { User } from "@/api/types";

export const meQuery = queryOptions({
  queryKey: ["auth", "me"],
  // 未登录时返回 null，而不是报错
  queryFn: async (): Promise<User | null> => {
    try {
      return (await api.get<User>("/auth/me")).data;
    } catch (error) {
      if (isUnauthorized(error)) return null;
      throw error;
    }
  },
  staleTime: 5 * 60_000,
});

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { username: string; password: string }) =>
      (await api.post<User>("/auth/login", body)).data,
    onSuccess: (user) => queryClient.setQueryData(meQuery.queryKey, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(meQuery.queryKey, null);
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { code: string; username: string; password: string }) =>
      (await api.post<User>("/auth/register", body)).data,
    // 注册成功即已登录
    onSuccess: (user) => queryClient.setQueryData(meQuery.queryKey, user),
  });
}
