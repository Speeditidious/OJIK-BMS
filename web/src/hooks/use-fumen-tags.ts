import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Tag {
  id: string;
  tag: string;
}

export function useFumenTags(hash: string | null) {
  return useQuery<Tag[]>({
    queryKey: ["fumen-tags", hash],
    queryFn: () => api.get(`/fumens/${hash}/tags`),
    enabled: !!hash,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMyTags() {
  return useQuery<string[]>({
    queryKey: ["my-fumen-tags"],
    queryFn: () => api.get("/fumens/my-tags"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAddFumenTag(hash: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tag: string) => api.post(`/fumens/${hash}/tags`, { tag }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fumen-tags", hash] });
      queryClient.invalidateQueries({ queryKey: ["my-fumen-tags"] });
    },
  });
}

export function useDeleteFumenTag(hash: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) => api.delete(`/fumens/${hash}/tags/${tagId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fumen-tags", hash] });
    },
  });
}

export function useReorderFumenTags(hash: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tagIds: string[]) =>
      api.put(`/fumens/${hash}/tags/reorder`, { tag_ids: tagIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fumen-tags", hash] });
    },
  });
}
