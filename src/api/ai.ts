import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AiCapabilityId,
  AiCapabilityUpdate,
  AiModelList,
  AiProviderId,
  AiSettings,
  AiTestResult,
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
