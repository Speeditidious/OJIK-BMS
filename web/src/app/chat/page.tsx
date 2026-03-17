"use client";

import { useState } from "react";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Bot, Send, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "안녕하세요! OJIK BMS AI 어시스턴트입니다. BMS 관련 질문이나 플레이 기록 조회, 곡 추천 등을 도와드릴게요.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Add placeholder assistant message
    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      const { api } = await import("@/lib/api");

      let accumulated = "";
      for await (const chunk of api.stream("/chatbot/chat", {
        message: userMessage.content,
      })) {
        try {
          const parsed = JSON.parse(chunk);
          if (parsed.type === "token") {
            accumulated += parsed.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: accumulated } : m
              )
            );
          }
        } catch {
          // ignore parse errors for non-JSON chunks
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: "오류가 발생했습니다. 다시 시도해주세요." }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 py-6 flex flex-col max-w-3xl">
        <div className="flex items-center gap-3 mb-6">
          <Bot className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">AI 챗봇</h1>
        </div>

        {/* Messages */}
        <Card className="flex-1 flex flex-col p-4 mb-4 overflow-hidden">
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-3 items-start",
                  msg.role === "user" ? "flex-row-reverse" : "flex-row"
                )}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  {msg.role === "user" ? (
                    <User className="h-4 w-4" />
                  ) : (
                    <Bot className="h-4 w-4" />
                  )}
                </div>
                <div
                  className={cn(
                    "rounded-lg px-4 py-2 max-w-[80%] text-sm",
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground"
                  )}
                >
                  {msg.content || (
                    <span className="animate-pulse text-muted-foreground">
                      입력 중...
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="BMS에 대해 무엇이든 물어보세요..."
              className="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={isLoading}
            />
            <Button type="submit" size="icon" disabled={isLoading || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
