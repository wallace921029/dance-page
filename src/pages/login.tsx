import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useLogin } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { StageAuthLayout, stageSubmitButtonClass } from "@/pages/stage/common";

/** 只允许跳回站内路径，防止 ?next= 被用来跳到外部网站 */
function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  useDocumentTitle("登录");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    login.mutate(
      { username: username.trim(), password },
      {
        onSuccess: (user) => {
          const next = safeNext(searchParams.get("next"));
          const home = user.role === "admin" ? "/admin/books" : "/";
          // 读者不能进 /admin，next 指向那里时回到书架
          navigate(next && (user.role === "admin" || !next.startsWith("/admin")) ? next : home, {
            replace: true,
          });
        },
      },
    );
  };

  return (
    <StageAuthLayout subtitle="登录后开始读绘本">
      <form onSubmit={submit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="username">用户名</FieldLabel>
            <Input
              id="username"
              autoComplete="username"
              autoCapitalize="none"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="password">密码</FieldLabel>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          {login.isError && <FieldError>{getErrorMessage(login.error)}</FieldError>}
          <Field>
            <Button
              type="submit"
              size="lg"
              className={stageSubmitButtonClass}
              disabled={login.isPending}
            >
              {login.isPending && <Spinner />}
              登录
            </Button>
            <FieldDescription className="text-center">
              还没有账号？请向管理员要一个邀请码。
            </FieldDescription>
          </Field>
        </FieldGroup>
      </form>
    </StageAuthLayout>
  );
}
