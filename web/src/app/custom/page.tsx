import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ListMusic, Plus } from "lucide-react";

export default function CustomPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <ListMusic className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">커스텀 테이블 / 코스</h1>
          </div>
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            새로 만들기
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Custom Tables */}
          <div>
            <h2 className="text-xl font-semibold mb-4">커스텀 난이도표</h2>
            <Card className="border-dashed">
              <CardHeader>
                <CardTitle className="text-muted-foreground text-base">
                  + 새 난이도표 만들기
                </CardTitle>
                <CardDescription>
                  나만의 BMS 난이도표를 만들고 곡을 정리하세요
                </CardDescription>
              </CardHeader>
            </Card>
          </div>

          {/* Custom Courses */}
          <div>
            <h2 className="text-xl font-semibold mb-4">커스텀 코스</h2>
            <Card className="border-dashed">
              <CardHeader>
                <CardTitle className="text-muted-foreground text-base">
                  + 새 코스 만들기
                </CardTitle>
                <CardDescription>
                  여러 곡을 묶어 코스를 만들고 LR2/Beatoraja 형식으로 내보내세요
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
