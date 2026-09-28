import { useState } from "react";
import { ChevronDown, CircleAlert, CircleCheck, Info, KeyRound, PlugZap } from "lucide-react";
import { cn } from "cn";
import { useAiModels, useAiSettings, useTestAiCapability, useUpdateAiCapability } from "@/api/ai";
import type {
  AiCapability,
  AiCapabilityId,
  AiProvider,
  AiProviderConfig,
  AiProviderId,
  AiTestResult,
  AiVideoOptions,
} from "@/api/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { PageHeader } from "@/pages/admin/layout";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

export default function AdminAiSettingsPage() {
  const { data: settings, isPending, error } = useAiSettings();
  useDocumentTitle("AI 配置");

  return (
    <>
      <PageHeader
        title="AI 配置"
        description="绘本的故事分析、朗读和动画由这里配置的服务生成，费用从你的服务商账户扣除。"
      />
      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <div className="space-y-8">
          <section>
            <h2 className="font-medium">服务商</h2>
            <p className="mt-1 mb-3 text-sm text-muted-foreground">
              API Key 写在服务器的 .env 文件里，修改后重启服务生效；这里只显示是否已设置和末 4
              位。两家都填好后，下面每项能力可以随时切换服务商。
            </p>
            <ProvidersCard providers={settings.providers} />
          </section>

          <section>
            <h2 className="font-medium">能力</h2>
            <p className="mt-1 mb-3 text-sm text-muted-foreground">
              每项能力分别选择服务商和模型。切换服务商不影响已经生成的朗读和动画。
            </p>
            <div className="space-y-4">
              {settings.capabilities.map((capability) => (
                <CapabilityCard
                  key={capability.id}
                  capability={capability}
                  providers={settings.providers}
                />
              ))}
            </div>
          </section>
        </div>
      )}
    </>
  );
}

// ---------- 服务商凭据 ----------

function ProvidersCard({ providers }: { providers: AiProvider[] }) {
  return (
    <Card>
      <CardContent>
        <Tabs defaultValue={providers[0].id}>
          <TabsList>
            {providers.map((provider) => {
              const setCount = provider.fields.filter((f) => f.is_set).length;
              return (
                <TabsTrigger key={provider.id} value={provider.id}>
                  <KeyRound />
                  {provider.name}
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {setCount}/{provider.fields.length}
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>
          {providers.map((provider) => (
            <TabsContent key={provider.id} value={provider.id} className="pt-4">
              <FieldGroup>
                {provider.fields.map((field) => (
                  <Field key={field.key}>
                    <FieldTitle>
                      {field.label}
                      {field.is_set ? (
                        <Badge variant="secondary" className="font-mono">
                          {field.preview}
                        </Badge>
                      ) : (
                        <Badge variant="outline">未设置</Badge>
                      )}
                    </FieldTitle>
                    <FieldDescription>
                      <code className="font-mono text-foreground">{field.env_var}</code> ·{" "}
                      {field.help}
                    </FieldDescription>
                  </Field>
                ))}
              </FieldGroup>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}

// ---------- 能力 ----------

type Draft = {
  provider: AiProviderId;
  model: string;
  baseUrl: string;
  duration?: number;
  resolution?: string;
};

function draftFrom(config: AiProviderConfig): Draft {
  return {
    provider: config.provider,
    model: config.model,
    baseUrl: config.base_url,
    duration: config.options.duration,
    resolution: config.options.resolution,
  };
}

function videoOptionsFor(config: AiProviderConfig, model: string): AiVideoOptions | null {
  return config.video_models[model.trim()] ?? config.video_fallback;
}

/** 换了模型后，时长和清晰度不在新模型的可选范围内时改用新模型的默认值 */
function fitVideoOptions(draft: Draft, options: AiVideoOptions | null): Draft {
  if (!options) return draft;
  return {
    ...draft,
    duration: options.durations.includes(draft.duration ?? -1)
      ? draft.duration
      : options.default_duration,
    resolution: options.resolutions.includes(draft.resolution ?? "")
      ? draft.resolution
      : options.default_resolution,
  };
}

function CapabilityCard({
  capability,
  providers,
}: {
  capability: AiCapability;
  providers: AiProvider[];
}) {
  const configOf = (provider: AiProviderId) =>
    capability.configs.find((c) => c.provider === provider)!;
  const active = configOf(capability.provider);
  const update = useUpdateAiCapability(capability.id);
  const test = useTestAiCapability(capability.id);
  const [draft, setDraft] = useState<Draft>(() => draftFrom(active));

  const config = configOf(draft.provider);
  const video = capability.id === "video" ? videoOptionsFor(config, draft.model) : null;
  const saved = draftFrom(active);
  const dirty =
    draft.provider !== saved.provider ||
    draft.model.trim() !== saved.model ||
    draft.baseUrl.trim().replace(/\/+$/, "") !== saved.baseUrl ||
    (video !== null &&
      (draft.duration !== saved.duration || draft.resolution !== saved.resolution));
  const providerName = (id: AiProviderId) => providers.find((p) => p.id === id)!.name;
  const providerItems = providers.map((p) => ({ value: p.id, label: p.name }));

  const change = (next: Draft) => {
    setDraft(next);
    test.reset();
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    update.mutate(
      {
        provider: draft.provider,
        model: draft.model,
        base_url: draft.baseUrl,
        options: video ? { duration: draft.duration, resolution: draft.resolution } : {},
      },
      {
        onSuccess: (settings) => {
          const saved = settings.capabilities
            .find((c) => c.id === capability.id)!
            .configs.find((c) => c.provider === draft.provider)!;
          setDraft(draftFrom(saved));
          toast.add({ title: `${capability.name}已保存`, type: "success" });
        },
        onError: (err) =>
          toast.add({ title: "保存失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const runTest = () =>
    test.mutate(undefined, {
      onError: (err) =>
        toast.add({ title: "无法测试", description: getErrorMessage(err), type: "error" }),
    });

  return (
    <Card>
      <form onSubmit={save} className="contents">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {capability.name}
            <Badge variant="secondary">当前：{providerName(capability.provider)}</Badge>
          </CardTitle>
          <CardDescription>{capability.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor={`${capability.id}-provider`}>服务商</FieldLabel>
              <Select
                items={providerItems}
                value={draft.provider}
                onValueChange={(value) => {
                  if (value === null) return;
                  // 切换服务商时显示那家已保存的设置（没保存过则是默认值）
                  change(draftFrom(configOf(value)));
                }}
              >
                <SelectTrigger id={`${capability.id}-provider`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {providerItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor={`${capability.id}-model`}>模型</FieldLabel>
              <ModelInput
                id={`${capability.id}-model`}
                capability={capability.id}
                provider={draft.provider}
                value={draft.model}
                onChange={(model) => {
                  const next = { ...draft, model };
                  change(video ? fitVideoOptions(next, videoOptionsFor(config, model)) : next);
                }}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor={`${capability.id}-base-url`}>Base URL</FieldLabel>
              <Input
                id={`${capability.id}-base-url`}
                value={draft.baseUrl}
                spellCheck={false}
                onChange={(e) => change({ ...draft, baseUrl: e.target.value })}
              />
              <FieldDescription>
                一般不用改。默认：<span className="font-mono">{config.default_base_url}</span>
              </FieldDescription>
            </Field>
            {video && (
              <>
                <OptionSelect
                  id={`${capability.id}-duration`}
                  label="默认时长"
                  value={draft.duration ?? video.default_duration}
                  items={video.durations.map((d) => ({ value: d, label: `${d} 秒` }))}
                  onChange={(duration) => change({ ...draft, duration })}
                />
                <OptionSelect
                  id={`${capability.id}-resolution`}
                  label="默认清晰度"
                  value={draft.resolution ?? video.default_resolution}
                  items={video.resolutions.map((r) => ({ value: r, label: r }))}
                  onChange={(resolution) => change({ ...draft, resolution })}
                />
                <FieldDescription className="sm:col-span-2">
                  可选范围取决于所选模型；生成某个开页的动画时还可以临时修改。
                </FieldDescription>
              </>
            )}
          </FieldGroup>

          {config.missing_credentials.length > 0 && (
            <Alert>
              <Info />
              <AlertDescription>
                还需要在服务器的 .env 中设置{" "}
                <span className="font-mono">{config.missing_credentials.join("、")}</span>
                ，然后重启服务。
              </AlertDescription>
            </Alert>
          )}
          {test.data && <TestResultAlert result={test.data} />}
        </CardContent>
        <CardFooter className="justify-end gap-2">
          {dirty && <span className="mr-auto text-sm text-muted-foreground">有未保存的修改</span>}
          <Button
            type="button"
            variant="outline"
            // 测试的是已保存的设置
            disabled={dirty || test.isPending || active.missing_credentials.length > 0}
            onClick={runTest}
          >
            {test.isPending ? <Spinner /> : <PlugZap />}
            测试连接
          </Button>
          <Button type="submit" disabled={!dirty || update.isPending}>
            {update.isPending && <Spinner />}
            保存
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

/** 模型名：可以手动输入，也可以从服务商的模型列表（合并内置推荐）里选 */
function ModelInput({
  id,
  capability,
  provider,
  value,
  onChange,
}: {
  id: string;
  capability: AiCapabilityId;
  provider: AiProviderId;
  value: string;
  onChange: (model: string) => void;
}) {
  const [open, setOpen] = useState(false);
  // 打开列表时才向服务商请求
  const models = useAiModels(capability, provider, open);

  return (
    <InputGroup>
      <InputGroupInput
        id={id}
        value={value}
        spellCheck={false}
        placeholder="手动输入，或从右侧列表选择"
        onChange={(e) => onChange(e.target.value)}
      />
      <InputGroupAddon align="inline-end">
        <DropdownMenu open={open} onOpenChange={setOpen}>
          <DropdownMenuTrigger render={<InputGroupButton title="从服务商获取模型列表" />}>
            选择模型
            <ChevronDown />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="max-h-80 w-auto max-w-[min(34rem,90vw)] min-w-80 overflow-y-auto"
          >
            {models.isPending ? (
              <DropdownMenuGroup>
                <DropdownMenuLabel className="flex items-center gap-2">
                  <Spinner />
                  正在从服务商获取…
                </DropdownMenuLabel>
              </DropdownMenuGroup>
            ) : models.error ? (
              <DropdownMenuGroup>
                <DropdownMenuLabel className="text-destructive">
                  {getErrorMessage(models.error)}
                </DropdownMenuLabel>
              </DropdownMenuGroup>
            ) : (
              <>
                {models.data.message && (
                  <>
                    <DropdownMenuGroup>
                      <DropdownMenuLabel className="font-normal whitespace-normal">
                        {models.data.message}
                      </DropdownMenuLabel>
                    </DropdownMenuGroup>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
                  {models.data.models.map((model) => (
                    <DropdownMenuRadioItem key={model.id} value={model.id} closeOnClick>
                      <span
                        className={cn(
                          "font-mono whitespace-nowrap",
                          model.retiring && "text-muted-foreground",
                        )}
                      >
                        {model.id}
                      </span>
                      {model.note && (
                        <Badge
                          variant={model.retiring ? "outline" : "secondary"}
                          className="ml-auto"
                        >
                          {model.note}
                        </Badge>
                      )}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </InputGroupAddon>
    </InputGroup>
  );
}

function OptionSelect<T extends string | number>({
  id,
  label,
  value,
  items,
  onChange,
}: {
  id: string;
  label: string;
  value: T;
  items: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Select items={items} value={value} onValueChange={(v) => v !== null && onChange(v)}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}

function TestResultAlert({ result }: { result: AiTestResult }) {
  if (result.status === "failed") {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>连接失败</AlertTitle>
        <AlertDescription>{result.message}</AlertDescription>
      </Alert>
    );
  }
  return (
    <Alert>
      {result.status === "ok" ? <CircleCheck /> : <Info />}
      <AlertTitle>{result.status === "ok" ? "连接正常" : "暂不支持测试"}</AlertTitle>
      <AlertDescription>{result.message}</AlertDescription>
    </Alert>
  );
}
