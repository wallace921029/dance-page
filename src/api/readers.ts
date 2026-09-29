import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Reader } from "@/api/types";

const readersKey = ["admin", "readers"] as const;

export function useReaders() {
  return useQuery({
    queryKey: readersKey,
    queryFn: async () => (await api.get<Reader[]>("/admin/readers")).data,
  });
}

export function useSetReaderDisabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, disabled }: { id: number; disabled: boolean }) =>
      (await api.patch<Reader>(`/admin/readers/${id}`, { is_disabled: disabled })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: readersKey }),
  });
}

/** 授予 / 取消小小管理员（只有管理员能做，立即生效，D109） */
export function useSetReaderRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, role }: { id: number; role: Reader["role"] }) =>
      (await api.patch<Reader>(`/admin/readers/${id}`, { role })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: readersKey }),
  });
}

export function useResetReaderPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) =>
      api.post(`/admin/readers/${id}/reset-password`, { password }),
  });
}
