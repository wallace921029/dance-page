import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReaderBook, ShelfBook } from "@/api/types";

export function useShelf() {
  return useQuery({
    queryKey: ["shelf"],
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
