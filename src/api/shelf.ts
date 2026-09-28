import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReaderBook, ShelfBook } from "@/api/types";

const shelfKey = ["shelf"] as const;

export function useShelf() {
  return useQuery({
    queryKey: shelfKey,
    queryFn: async () => (await api.get<ShelfBook[]>("/books")).data,
  });
}

export function useReaderBook(id: string) {
  return useQuery({
    queryKey: ["shelf", id],
    queryFn: async () => (await api.get<ReaderBook>(`/books/${id}`)).data,
    // 404（书被删除或下架）不必重试
    retry: false,
  });
}

/** 收藏 / 取消收藏（D55）。先更新界面再请求，失败时回滚 */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, favorite }: { id: string; favorite: boolean }) =>
      favorite ? api.put(`/books/${id}/favorite`) : api.delete(`/books/${id}/favorite`),
    onMutate: async ({ id, favorite }) => {
      await queryClient.cancelQueries({ queryKey: shelfKey, exact: true });
      const previous = queryClient.getQueryData<ShelfBook[]>(shelfKey);
      const favoritedAt = favorite ? new Date().toISOString() : null;
      queryClient.setQueryData<ShelfBook[]>(shelfKey, (books) =>
        books?.map((b) =>
          b.id === id ? { ...b, is_favorite: favorite, favorited_at: favoritedAt } : b,
        ),
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(shelfKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: shelfKey }),
  });
}
