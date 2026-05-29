import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Issue,
  IssueComment,
  IssueCreate,
  IssueIssueSearchResult,
  IssueSearchField,
  IssueSortKey,
  IssueStatus,
  IssueStatusCounts,
  IssueTag,
  IssueUserSearchResult,
  Pagination,
} from "@/types";

export function useIssueTags() {
  return useQuery<IssueTag[]>({
    queryKey: ["issues", "tags"],
    queryFn: () => api.get("/issues/tags"),
  });
}

export function useIssues(params: {
  page: number;
  size: number;
  q?: string;
  search_field?: IssueSearchField;
  tag?: string;
  status?: IssueStatus | "all";
  sort?: IssueSortKey;
}) {
  return useQuery<Pagination<Issue>>({
    queryKey: ["issues", "list", params],
    queryFn: () => {
      const search = new URLSearchParams({
        page: String(params.page),
        size: String(params.size),
      });
      if (params.q) search.set("q", params.q);
      if (params.search_field) search.set("search_field", params.search_field);
      if (params.tag) search.set("tag", params.tag);
      if (params.status) search.set("status", params.status);
      if (params.sort) search.set("sort", params.sort);
      return api.get(`/issues/?${search.toString()}`);
    },
  });
}

export function useIssueCounts(params: {
  q?: string;
  search_field?: IssueSearchField;
  tag?: string;
}) {
  return useQuery<IssueStatusCounts>({
    queryKey: ["issues", "counts", params],
    queryFn: () => {
      const search = new URLSearchParams();
      if (params.q) search.set("q", params.q);
      if (params.search_field) search.set("search_field", params.search_field);
      if (params.tag) search.set("tag", params.tag);
      const qs = search.toString();
      return api.get(qs ? `/issues/counts?${qs}` : `/issues/counts`);
    },
  });
}

export function useIssue(issueId: number | null) {
  return useQuery<Issue>({
    queryKey: ["issues", issueId],
    queryFn: () => api.get(`/issues/${issueId}`),
    enabled: issueId !== null,
  });
}

export function useIssueComments(issueId: number | null, page: number, size: number) {
  return useQuery<Pagination<IssueComment>>({
    queryKey: ["issues", issueId, "comments", page, size],
    queryFn: () => api.get(`/issues/${issueId}/comments?page=${page}&size=${size}`),
    enabled: issueId !== null,
  });
}

export function useCreateIssue() {
  const queryClient = useQueryClient();
  return useMutation<Issue, Error, IssueCreate>({
    mutationFn: (data) => api.post("/issues/", data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["issues"] }),
  });
}

export function useCreateIssueComment(issueId: number) {
  const queryClient = useQueryClient();
  return useMutation<IssueComment, Error, { body: string }>({
    mutationFn: (data) => api.post(`/issues/${issueId}/comments`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", "list"] });
      queryClient.invalidateQueries({ queryKey: ["issues", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issues", issueId, "comments"] });
    },
  });
}

export function useUpdateIssueStatus(issueId: number) {
  const queryClient = useQueryClient();
  return useMutation<Issue, Error, { status: IssueStatus }>({
    mutationFn: (data) => api.patch(`/issues/${issueId}/status`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", "list"] });
      queryClient.invalidateQueries({ queryKey: ["issues", "counts"] });
      queryClient.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export function useSearchIssueUsers(q: string, enabled: boolean) {
  return useQuery<IssueUserSearchResult[]>({
    queryKey: ["issues", "search", "users", q],
    queryFn: () => api.get(`/issues/search/users?q=${encodeURIComponent(q)}`),
    enabled: enabled && q.length > 0,
    staleTime: 10_000,
  });
}

export function useSearchIssues(q: string, enabled: boolean) {
  return useQuery<IssueIssueSearchResult[]>({
    queryKey: ["issues", "search", "issues", q],
    queryFn: () => api.get(`/issues/search/issues?q=${encodeURIComponent(q)}`),
    enabled: enabled && q.length > 0,
    staleTime: 10_000,
  });
}

export function usePinnedIssues(size = 5) {
  return useQuery<Issue[]>({
    queryKey: ["issues", "pinned", size],
    queryFn: () => api.get(`/issues/pinned?size=${size}`),
  });
}

export function useUpdateIssuePinned(issueId: number) {
  const queryClient = useQueryClient();
  return useMutation<Issue, Error, { is_pinned: boolean }>({
    mutationFn: (data) => api.patch(`/issues/${issueId}/pin`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", "list"] });
      queryClient.invalidateQueries({ queryKey: ["issues", "pinned"] });
      queryClient.invalidateQueries({ queryKey: ["issues", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issues", issueId, "comments"] });
    },
  });
}

export function useUpdateIssueBody(issueId: number) {
  const queryClient = useQueryClient();
  return useMutation<Issue, Error, { body: string }>({
    mutationFn: (data) => api.patch(`/issues/${issueId}/body`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export function useUpdateIssueComment(issueId: number, commentId: string) {
  const queryClient = useQueryClient();
  return useMutation<IssueComment, Error, { body: string }>({
    mutationFn: (data) => api.patch(`/issues/${issueId}/comments/${commentId}/body`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", issueId, "comments"] });
    },
  });
}
