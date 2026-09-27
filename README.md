# Vite + React + TypeScript Template

现代化的前端工程化脚手架模板，集成 React 19、TypeScript、Vite 8、Tailwind CSS v4 以及 shadcn/ui 组件库。

## 技术栈特性

- **核心框架**：[React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- **构建工具**：[Vite 8](https://vite.dev/)（极速冷启动与 HMR 热重载）
- **样式方案**：[Tailwind CSS v4](https://tailwindcss.com/) + `@tailwindcss/vite` + [Geist Font](https://fontsource.org/fonts/geist)
- **UI 组件库**：[shadcn/ui](https://ui.shadcn.com/)（包含常用 UI 原语组件）+ [Lucide Icons](https://lucide.dev/)
- **路由方案**：[React Router](https://reactrouter.com/)
- **网络请求**：[Axios](https://axios-http.com/)（预置 API 客户端配置与开发代理）
- **代码规范**：[Oxlint](https://oxc.rs/docs/guide/usage/linter.html)（高性能代码检查）

## 目录结构

```text
.
├── backend/            # 后端目录（待从零构建，保留 .gitkeep）
├── public/             # 静态资源
├── src/
│   ├── components/     # 公共组件
│   │   └── ui/         # shadcn/ui 组件库
│   ├── hooks/          # 自定义 React Hooks（如 use-mobile）
│   ├── lib/            # 工具库（utils.ts、api.ts）
│   ├── pages/          # 页面模块（如 home.tsx）
│   ├── router/         # 路由配置
│   ├── index.css       # Tailwind CSS v4 主题与全局样式
│   └── main.tsx        # 应用主入口
├── components.json     # shadcn/ui 配置文件
├── index.html          # HTML 入口
├── package.json        # 项目依赖及脚本
├── tsconfig*.json      # TypeScript 编译器配置
└── vite.config.ts      # Vite 配置文件
```

## 快速上手

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

本地服务默认运行在 `http://localhost:5173`。

### 3. 代码检查与构建

```bash
# 执行代码质量检查 (Oxlint)
npm run lint

# TypeScript 类型检查并打包生产构建
npm run build

# 本地预览生产构建产物
npm run preview
```

## 开发指引

### 添加新页面与路由
在 `src/pages/` 下创建新的页面组件，并在 `src/router/index.tsx` 中注册对应路由。

### API 请求代理
在 `vite.config.ts` 中已预配置开发服务器代理：
```ts
server: {
  proxy: {
    "/api": "http://127.0.0.1:8000",
  },
}
```
业务请求可直接导入 `src/lib/api.ts` 中的 `api` 实例：
```ts
import { api } from "@/lib/api";

const res = await api.get("/users");
```
