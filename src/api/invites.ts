import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Invite } from "@/api/types";

const invitesKey = ["admin", "invites"] as const;

export function useInvites() {
  return useQuery({
    queryKey: invitesKey,
    queryFn: async () => (await api.get<Invite[]>("/admin/invites")).data,
  });
}

export function useCreateInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (validDays: number) =>
      (await api.post<Invite>("/admin/invites", { valid_days: validDays })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitesKey }),
  });
}

/** 删除没被用过的邀请码（未使用、已过期、已作废）；已使用的要保留 */
export function useDeleteInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/admin/invites/${id}`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitesKey }),
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post<Invite>(`/admin/invites/${id}/revoke`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitesKey }),
  });
}
