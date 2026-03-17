"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table2, Plus } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { TableSidebar } from "@/components/tables/TableSidebar";
import { TableDetail } from "@/components/tables/TableDetail";
import { ImportDialog } from "@/components/tables/ImportDialog";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/lib/api";
import type { DifficultyTable } from "@/types";

export default function TablesPage() {
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const { user } = useAuthStore();
  const isLoggedIn = !!user;

  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get("/tables/"),
    staleTime: 2 * 60 * 1000,
  });

  const { data: favorites = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["favorites"],
    queryFn: () => api.get("/tables/favorites/me"),
    enabled: isLoggedIn,
    staleTime: 2 * 60 * 1000,
  });

  const handleImported = (table: DifficultyTable) => {
    setSelectedTableId(table.id);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />

      <div className="flex items-center gap-3 px-6 py-4 border-b">
        <Table2 className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">난이도표 허브</h1>
        <div className="ml-auto flex items-center gap-2">
          {isLoggedIn && (
            <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              난이도표 추가
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 128px)" }}>
        {/* Sidebar */}
        <div className="w-64 shrink-0">
          <TableSidebar
            favorites={favorites}
            allTables={allTables}
            selectedId={selectedTableId}
            onSelect={setSelectedTableId}
            onImportClick={() => setImportOpen(true)}
            isLoggedIn={isLoggedIn}
          />
        </div>

        {/* Main panel */}
        <div className="flex-1 overflow-hidden">
          {selectedTableId !== null ? (
            <TableDetail tableId={selectedTableId} isLoggedIn={isLoggedIn} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
              <Table2 className="h-16 w-16 opacity-20" />
              <div className="text-center">
                <p className="font-medium">난이도표를 선택하세요</p>
                <p className="text-sm mt-1">
                  {allTables.length > 0
                    ? `${allTables.length}개의 난이도표가 있습니다`
                    : "난이도표를 불러오는 중..."}
                </p>
              </div>
              {!isLoggedIn && (
                <p className="text-xs">
                  로그인하면 즐겨찾기 기능을 사용할 수 있습니다.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <ImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={handleImported}
      />
    </div>
  );
}
