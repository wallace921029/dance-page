import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useRegister } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { StageAuthLayout, stageSubmitButtonClass } from "@/pages/stage/common";

// 与后端规则一致（D44），提前在前端提示
const USERNAME_PATTERN = /^[A-Za-z0-9_一-鿿]{2,20}$/;
const PASSWORD_MIN_LENGTH = 6;

function validate(username: string, password: string, confirm: string): string | null {
  if (!USERNAME_PATTERN.test(username)) return "用户名需为 2–20 位中文、字母、数字或下划线";
  if (password.length < PASSWORD_MIN_LENGTH) return `密码至少 ${PASSWORD_MIN_LENGTH} 位`;
  if (password !== confirm) return "两次输入的密码不一致";
  return null;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const register = useRegister();
  const [code, setCode] = useState(searchParams.get("code") ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  useDocumentTitle("注册");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const error = validate(username.trim(), password, confirm);
    setFormError(error);
    if (error) return;
    register.mutate(
      { code, username: username.trim(), password },
      { onSuccess: () => navigate("/", { replace: true }) },
    );
  };

  const error = formError ?? (register.isError ? getErrorMessage(register.error) : null);

  return (
    <StageAuthLayout subtitle="用邀请码注册，开始读绘本">
      <form onSubmit={submit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="code">邀请码</FieldLabel>
            <Input
              id="code"
              autoComplete="off"
              autoCapitalize="characters"
              placeholder="如 K7M3-Q9TX"
              className="font-mono tracking-wider uppercase"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="username">用户名</FieldLabel>
            <Input
              id="username"
              autoComplete="username"
              autoCapitalize="none"
              placeholder="2–20 位中文、字母、数字或下划线"
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
              autoComplete="new-password"
              placeholder={`至少 ${PASSWORD_MIN_LENGTH} 位`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="confirm">确认密码</FieldLabel>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </Field>
          {error && <FieldError>{error}</FieldError>}
          <Field>
            <Button
              type="submit"
              size="lg"
              className={stageSubmitButtonClass}
              disabled={register.isPending}
            >
              {register.isPending && <Spinner />}
              注册
            </Button>
            <FieldDescription className="text-center">
              已有账号？
              <Button
                variant="link"
                nativeButton={false}
                render={<Link to="/login" />}
                className="h-auto p-0 text-stage-light"
              >
                去登录
              </Button>
            </FieldDescription>
          </Field>
        </FieldGroup>
      </form>
    </StageAuthLayout>
  );
}
