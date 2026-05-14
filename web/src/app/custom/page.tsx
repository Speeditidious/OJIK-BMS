"use client";

import { useTranslation } from "react-i18next";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ListMusic, Plus } from "lucide-react";

export default function CustomPage() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <ListMusic className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">{t("custom.title")}</h1>
          </div>
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            {t("custom.create")}
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Custom Tables */}
          <div>
            <h2 className="text-xl font-semibold mb-4">{t("custom.tablesTitle")}</h2>
            <Card className="border-dashed">
              <CardHeader>
                <CardTitle className="text-muted-foreground text-base">
                  {t("custom.newTable")}
                </CardTitle>
                <CardDescription>
                  {t("custom.tableDescription")}
                </CardDescription>
              </CardHeader>
            </Card>
          </div>

          {/* Custom Courses */}
          <div>
            <h2 className="text-xl font-semibold mb-4">{t("custom.coursesTitle")}</h2>
            <Card className="border-dashed">
              <CardHeader>
                <CardTitle className="text-muted-foreground text-base">
                  {t("custom.newCourse")}
                </CardTitle>
                <CardDescription>
                  {t("custom.courseDescription")}
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
