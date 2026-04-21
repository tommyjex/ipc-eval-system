import { useEffect, useState } from 'react';
import { createBrowserRouter, RouterProvider, Link, Outlet, Navigate, useNavigate } from 'react-router-dom';
import { authApi } from './api';
import { DatasetListPage } from './pages/datasets/DatasetListPage';
import { DatasetCreatePage } from './pages/datasets/DatasetCreatePage';
import { DatasetDetailPage } from './pages/datasets/DatasetDetailPage';
import { TaskListPage } from './pages/tasks/TaskListPage';
import { TaskDetailPage } from './pages/tasks/TaskDetailPage';
import { TaskComparePage } from './pages/tasks/TaskComparePage';
import { LoginPage } from './pages/LoginPage';
import { UserManagementPage } from './pages/users/UserManagementPage';

const HOME_HERO_IMAGE = 'https://xujianhua-utils.tos-cn-beijing.volces.com/AI-IPC/frontend-assets/home_hero_v2.png';
const PLATFORM_LOGO = 'https://xujianhua-utils.tos-cn-beijing.volces.com/AI-IPC/frontend-assets/visual_intelligence_logo.png';
const HOME_NAV_LINKS = [
  {
    title: 'AI视觉智能行业弹药库',
    description: '沉淀视觉智能行业分析、业务打法、案例和材料，方便统一查阅与复用。',
    href: 'https://bytedance.larkoffice.com/docx/JODVd2N6uoh0toxKQ9ncInrynfe',
  },
  {
    title: '视觉智能行业 OnePage',
    description:
      '智能云存和智能消息告警已进入成熟阶段；AI IPC、arkclaw IPC处于产品打磨探索期；智能巡检面向小B，仍在 0-1 阶段。',
    href: 'https://bytedance.larkoffice.com/docx/NxEXdDM2doEotAxx4MSchbypnbe',
  },
  {
    title: '智能云存解决方案',
    description: '聚焦家庭与安防场景的智能云存能力，支撑规模化复制与方案落地。',
    href: 'https://bytedance.larkoffice.com/docx/Ct9XdTXjioXTLoxED9Qc0A23nfd',
  },
  {
    title: '智能消息告警解决方案',
    description:
      '围绕 IPC 安防告警体验优化，减少高频无效通知，提升真正值得关注事件的识别与推送质量。',
    href: 'https://bytedance.larkoffice.com/docx/Gr1UdseDko95qTx2V9XcN9LBneg?from=navigation',
  },
  {
    title: 'AI IPC解决方案',
    description:
      '涵盖 AI 音视频互动智能体、A2A、门锁与摄像头联动、跨端协同及联网问答等能力，聚焦高价值家庭智能场景。',
    href: 'https://bytedance.larkoffice.com/docx/ApL2dpptBouDAAxcYMlc7xVCneg',
  },
  {
    title: '视觉智能行业 ArkClaw 的应用',
    description:
      'ArkClaw 在 IPC 领域可作为设备控制枢纽，将设备控制能力封装为 Skill，并在用户提问时自主决策调用与编排，支持如“帮忙找到家里的小孩，看他在做什么”这类复杂任务。',
    href: 'https://bytedance.larkoffice.com/docx/Om6PdRKs9ovi2fxPDU6cHelOnyc',
  },
];

function Layout({ username }: { username: string }) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/" className="flex items-center">
                <img 
                  src={PLATFORM_LOGO}
                  alt="Logo" 
                  className="h-10 w-auto mr-4"
                />
                <span className="text-xl font-bold text-gray-900">视觉智能评测平台</span>
              </Link>
              <div className="ml-10 flex items-center space-x-4">
                <Link to="/datasets" className="text-gray-600 hover:text-gray-900 px-3 py-2">
                  评测集管理
                </Link>
                <Link to="/tasks" className="text-gray-600 hover:text-gray-900 px-3 py-2">
                  评测任务
                </Link>
                <Link to="/users" className="text-gray-600 hover:text-gray-900 px-3 py-2">
                  用户管理
                </Link>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">{username}</span>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await authApi.logout();
                  } finally {
                    navigate('/login', { replace: true });
                  }
                }}
                className="rounded border px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
      <footer className="border-t bg-white px-4 py-4 text-center text-sm text-gray-500 sm:px-6 lg:px-8">
        Powered by 火山引擎行业解决方案团队 视觉智能专项小组
      </footer>
    </div>
  );
}

function ProtectedLayout() {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState('');

  useEffect(() => {
    const checkLogin = async () => {
      try {
        const user = await authApi.me();
        setAuthenticated(true);
        setUsername(user.username);
      } catch {
        setAuthenticated(false);
        setUsername('');
      } finally {
        setChecking(false);
      }
    };
    checkLogin();
  }, []);

  if (checking) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-100">检查登录状态中...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Layout username={username} />;
}

function HomePage() {
  return (
    <div className="px-4 py-6 sm:px-6 lg:px-8">
      <div className="overflow-hidden rounded-3xl bg-slate-900 shadow-xl">
        <div
          className="relative"
          style={{
            backgroundImage: `linear-gradient(90deg, rgba(15,23,42,0.92) 0%, rgba(15,23,42,0.72) 42%, rgba(15,23,42,0.18) 100%), url(${HOME_HERO_IMAGE})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        >
          <div className="max-w-7xl px-8 py-20 sm:px-10 lg:px-14">
            <div className="max-w-2xl">
              <div className="mb-4 inline-flex rounded-full border border-white/15 bg-white/10 px-4 py-1 text-sm text-blue-100 backdrop-blur">
                视觉智能 · 家庭安防 · 多模型评测
              </div>
              <h1 className="whitespace-nowrap text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl">
                欢迎使用视觉智能大模型评测平台
              </h1>
              <p className="mt-5 text-lg leading-8 text-slate-200">
                统一管理评测集、标注数据与多模型评测任务，快速完成召回率、准确率对比分析，支撑家庭智能和安防类场景的模型验证。
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link
                  to="/datasets"
                  className="inline-flex items-center rounded-lg bg-blue-600 px-6 py-3 text-base font-medium text-white hover:bg-blue-700"
                >
                  开始使用
                </Link>
                <Link
                  to="/tasks"
                  className="inline-flex items-center rounded-lg border border-white/20 bg-white/10 px-6 py-3 text-base font-medium text-white hover:bg-white/15"
                >
                  查看任务
                </Link>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 bg-white px-6 py-8 sm:grid-cols-2 lg:grid-cols-3 lg:px-8">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-6 shadow-sm">
            <div className="mb-3 text-sm font-medium text-blue-600">Dataset</div>
            <h3 className="text-lg font-semibold text-gray-900">评测集管理</h3>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              创建和管理视频、图片类型的评测集，支持本地上传与 TOS 导入，适配家庭智能与安防场景素材管理。
            </p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-6 shadow-sm">
            <div className="mb-3 text-sm font-medium text-emerald-600">Annotation</div>
            <h3 className="text-lg font-semibold text-gray-900">数据标注</h3>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              支持人工标注和大模型自动标注，批量提升数据准备效率，为后续评测提供稳定可靠的标准答案。
            </p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-6 shadow-sm">
            <div className="mb-3 text-sm font-medium text-orange-600">Evaluation</div>
            <h3 className="text-lg font-semibold text-gray-900">模型评测</h3>
            <p className="mt-2 text-sm leading-6 text-gray-600">
              选择不同供应商与目标模型进行评测、打分和对比分析，快速定位召回率与准确率表现最优的模型。
            </p>
          </div>
        </div>
      </div>

      <div className="mt-10 rounded-3xl bg-white p-6 shadow-lg sm:p-8">
        <div className="mb-6">
          <div className="mb-2 text-sm font-medium uppercase tracking-[0.2em] text-blue-600">Resource Navigation</div>
          <h2 className="text-2xl font-bold text-gray-900">行业资料导航</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            汇总视觉智能相关的行业资料、解决方案与方向说明，方便登录后快速跳转查阅。
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {HOME_NAV_LINKS.map((item) => (
            <a
              key={item.title}
              href={item.href}
              target="_blank"
              rel="noreferrer"
              className="group rounded-2xl border border-slate-100 bg-slate-50 p-6 shadow-sm transition hover:border-blue-200 hover:bg-blue-50/40"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-700">{item.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-gray-600">{item.description}</p>
                </div>
                <span className="shrink-0 text-blue-500 transition group-hover:translate-x-1">↗</span>
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

const router = createBrowserRouter(
  [
    {
      path: '/login',
      element: <LoginPage />,
    },
    {
      path: '/',
      element: <ProtectedLayout />,
      children: [
        {
          index: true,
          element: <HomePage />,
        },
        {
          path: 'datasets',
          element: <DatasetListPage />,
        },
        {
          path: 'datasets/create',
          element: <DatasetCreatePage />,
        },
        {
          path: 'datasets/:id',
          element: <DatasetDetailPage />,
        },
        {
          path: 'tasks',
          element: <TaskListPage />,
        },
        {
          path: 'tasks/compare',
          element: <TaskComparePage />,
        },
        {
          path: 'tasks/:id',
          element: <TaskDetailPage />,
        },
        {
          path: 'users',
          element: <UserManagementPage />,
        },
      ],
    },
  ]
);

function App() {
  return <RouterProvider router={router} />;
}

export default App;
