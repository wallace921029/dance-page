// 生成动画时临时选择时长和清晰度的小弹窗（D79），封面动画和开页动画共用。
// 只对这一次生效；默认值在"AI 配置"里改。可选项跟随当前的视频模型（D77）
import { useState } from "react";
import { Settings2 } from "lucide-react";
import type { AiVideoOptions } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface VideoChoice {
  duration: number;
  resolution: string;
}

export function VideoOptionsPopover({
  options,
  disabled,
  onGenerate,
}: {
  options: AiVideoOptions;
  disabled?: boolean;
  onGenerate: (choice: VideoChoice) => void;
}) {
  const [open, setOpen] = useState(false);
  const [duration, setDuration] = useState(options.default_duration);
  const [resolution, setResolution] = useState(options.default_resolution);

  const handleOpenChange = (next: boolean) => {
    // 每次打开都从默认值开始
    if (next) {
      setDuration(options.default_duration);
      setResolution(options.default_resolution);
    }
    setOpen(next);
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <Button
            size="icon-xs"
            variant="ghost"
            aria-label="生成选项"
            title="选择时长和清晰度"
            disabled={disabled}
          />
        }
      >
        <Settings2 />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64">
        <PopoverHeader>
          <PopoverTitle>生成选项</PopoverTitle>
          <PopoverDescription>只对这一次生效，默认值在「AI 配置」里改。</PopoverDescription>
        </PopoverHeader>
        <ChoiceSelect
          label="时长"
          value={duration}
          items={options.durations.map((d) => ({ value: d, label: `${d} 秒` }))}
          onChange={setDuration}
        />
        <ChoiceSelect
          label="清晰度"
          value={resolution}
          items={options.resolutions.map((r) => ({ value: r, label: r }))}
          onChange={setResolution}
        />
        <Button
          size="sm"
          onClick={() => {
            setOpen(false);
            onGenerate({ duration, resolution });
          }}
        >
          按这个设置生成
        </Button>
      </PopoverContent>
    </Popover>
  );
}

function ChoiceSelect<T extends string | number>({
  label,
  value,
  items,
  onChange,
}: {
  label: string;
  value: T;
  items: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  const only = items.length === 1;
  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <Select
        items={items}
        value={value}
        onValueChange={(v) => v !== null && onChange(v)}
        disabled={only}
      >
        <SelectTrigger className="w-full" title={only ? "当前模型只支持这一个" : undefined}>
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
