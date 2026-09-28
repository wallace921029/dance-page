import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminBook, AdminBookDetail, BookUpdate } from "@/api/types";

const PROCESSING_POLL_MS = 2000;

export const adminBookKeys = {
  all: ["admin", "books"] as const,
  detail: (id: string) => ["admin", "books", id] as const,
};

export function useAdminBooks() {
  return useQuery({
    queryKey: adminBookKeys.all,
    queryFn: async () => (await api.get<AdminBook[]>("/admin/books")).data,
    // 有绘本在处理中时轮询进度
    refetchInterval: (query) =>
      query.state.data?.some((b) => b.processing_status === "processing")
        ? PROCESSING_POLL_MS
        : false,
  });
}

export function useAdminBook(id: string) {
  return useQuery({
    queryKey: adminBookKeys.detail(id),
    queryFn: async () => (await api.get<AdminBookDetail>(`/admin/books/${id}`)).data,
    refetchInterval: (query) =>
      query.state.data?.processing_status === "processing" ? PROCESSING_POLL_MS : false,
  });
}

export async function uploadBook(file: File, onProgress: (ratio: number) => void) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<AdminBook>("/admin/books", form, {
    onUploadProgress: (e) => e.total && onProgress(e.loaded / e.total),
  });
  return res.data;
}

export function useUpdateBook(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: BookUpdate) =>
      (await api.patch<AdminBookDetail>(`/admin/books/${id}`, body)).data,
    onSuccess: (book) => {
      queryClient.setQueryData(adminBookKeys.detail(id), book);
      queryClient.invalidateQueries({ queryKey: adminBookKeys.all, exact: true });
    },
  });
}

export function useDeleteBook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/admin/books/${id}`),
    onSuccess: (_data, id) => {
      // 只移除没有页面在用的缓存；详情页删除后会立刻跳走，移除正在使用的缓存会触发一次多余的请求（404）
      queryClient.removeQueries({ queryKey: adminBookKeys.detail(id), type: "inactive" });
      queryClient.invalidateQueries({ queryKey: adminBookKeys.all, exact: true });
    },
  });
}
