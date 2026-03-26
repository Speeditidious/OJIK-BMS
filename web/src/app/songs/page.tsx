import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Music2, Search } from "lucide-react";

export default function SongsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-8">
          <Music2 className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">차분 목록</h1>
        </div>

        {/* Search bar */}
        <div className="flex gap-2 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="곡명 또는 아티스트 검색..."
              className="w-full pl-9 pr-4 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <Button variant="outline">검색</Button>
        </div>

        {/* Song list placeholder */}
        <Card>
          <CardHeader>
            <CardTitle>서버에 기록된 차분 목록</CardTitle>
            <CardDescription>
              OJIK BMS 클라이언트로 동기화된 차분 목록
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-4">
              <Music2 className="h-12 w-12 opacity-30" />
              <p className="text-sm">구현 예정</p>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
