import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AiCapabilityId,
  AiCapabilityUpdate,
  AiModelList,
  AiProviderId,
  AiSettings,
  AiTestResult,
  BookAi,
  BookAiUpdateInput,
  Character,
  CharacterCreateInput,
  CharacterUpdateInput,
  Spread,
  AiUnit,
  UnitUpdateInput,
} from "@/api/types";

const aiSettingsKey = ["admin", "ai", "settings"] as const;

export function useAiSettings() {
  return useQuery({
    queryKey: aiSettingsKey,
    queryFn: async () => (await api.get<AiSettings>("/admin/ai/settings")).data,
  });
}

/** 保存该服务商的设置，并把这项能力切换到这家服务商 */
export function useUpdateAiCapability(capability: AiCapabilityId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AiCapabilityUpdate) =>
      (await api.put<AiSettings>(`/admin/ai/capabilities/${capability}`, body)).data,
    onSuccess: (settings) => queryClient.setQueryData(aiSettingsKey, settings),
  });
}

/** 用已保存的设置测试当前服务商能否连通 */
export function useTestAiCapability(capability: AiCapabilityId) {
  return useMutation({
    mutationFn: async () =>
      (await api.post<AiTestResult>(`/admin/ai/capabilities/${capability}/test`)).data,
  });
}

/** 这项能力在某家服务商上可选的模型（服务商列表 + 内置推荐）。只在打开选择列表时请求 */
export function useAiModels(capability: AiCapabilityId, provider: AiProviderId, enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "ai", "models", capability, provider],
    queryFn: async () =>
      (
        await api.get<AiModelList>(`/admin/ai/capabilities/${capability}/models`, {
          params: { provider },
        })
      ).data,
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------- 绘本 AI 工作台 Hooks ----------

export const bookAiKey = (bookId: string) => ["admin", "books", bookId, "ai"] as const;

export function useBookAi(bookId: string) {
  return useQuery({
    queryKey: bookAiKey(bookId),
    queryFn: async () => (await api.get<BookAi>(`/admin/books/${bookId}/ai`)).data,
    refetchInterval: (query) => (query.state.data?.running_jobs?.length ? 2000 : false),
  });
}

export function useUpdateBookAi(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: BookAiUpdateInput) =>
      (await api.patch<BookAi>(`/admin/books/${bookId}/ai`, body)).data,
    onSuccess: (data) => queryClient.setQueryData(bookAiKey(bookId), data),
  });
}

export function useAnalyzeBook(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      (await api.post<{ job_id: number; status: string }>(`/admin/books/${bookId}/ai/analyze`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useCreateCharacter(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CharacterCreateInput) =>
      (await api.post<Character>(`/admin/books/${bookId}/ai/characters`, body)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useUpdateCharacter(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: CharacterUpdateInput & { id: number }) =>
      (await api.patch<Character>(`/admin/books/${bookId}/ai/characters/${id}`, body)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useDeleteCharacter(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await api.delete(`/admin/books/${bookId}/ai/characters/${id}`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useUpdateSpreadMode(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ firstPage, mode }: { firstPage: number; mode: "separate" | "merged" }) =>
      (await api.put<Spread>(`/admin/books/${bookId}/ai/spreads/${firstPage}`, { mode })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useUpdateAiUnit(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ unitId, ...body }: UnitUpdateInput & { unitId: string }) =>
      (await api.patch<AiUnit>(`/admin/ai/units/${unitId}`, body)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

export function useDraftAiUnit(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (unitId: string) =>
      (await api.post<{ job_id: number; status: string }>(`/admin/ai/units/${unitId}/draft`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookAiKey(bookId) }),
  });
}

