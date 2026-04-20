import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api';

const LOGIN_HERO_IMAGE = 'https://xujianhua-utils.tos-cn-beijing.volces.com/AI-IPC/frontend-assets/login_hero.png';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const checkLogin = async () => {
      try {
        await authApi.me();
        navigate('/', { replace: true });
      } catch {
        // ignore
      } finally {
        setChecking(false);
      }
    };
    checkLogin();
  }, [navigate]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await authApi.login({ username, password });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-100">检查登录状态中...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="grid min-h-[calc(100vh-52px)] lg:grid-cols-[1.2fr_0.8fr]">
        <div
          className="relative hidden overflow-hidden lg:block"
          style={{
            backgroundImage: `linear-gradient(135deg, rgba(15,23,42,0.88) 0%, rgba(30,41,59,0.68) 45%, rgba(15,23,42,0.28) 100%), url(${LOGIN_HERO_IMAGE})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.22),transparent_38%)]" />
          <div className="relative flex h-full items-end px-12 py-16">
            <div className="max-w-xl">
              <div className="mb-4 inline-flex rounded-full border border-white/15 bg-white/10 px-4 py-1 text-sm text-blue-100 backdrop-blur">
                Visual Intelligence Evaluation
              </div>
              <h1 className="text-4xl font-bold tracking-tight text-white">
                视觉智能评测平台
              </h1>
              <p className="mt-5 text-lg leading-8 text-slate-200">
                聚焦家庭智能与安防场景，统一完成评测集管理、任务评测、智能评分与多模型对比分析。
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
          <div className="w-full max-w-md rounded-3xl bg-white p-8 shadow-2xl sm:p-10">
            <div className="mb-8">
              <div className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-blue-600">Admin Login</div>
              <h2 className="text-3xl font-bold text-gray-900">欢迎登录</h2>
              <p className="mt-3 text-sm leading-6 text-gray-600">
                请输入管理员账号和密码，进入视觉智能评测平台。
              </p>
            </div>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="username" className="mb-2 block text-sm font-medium text-gray-700">
                  账号
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  placeholder="请输入账号"
                  autoComplete="username"
                  required
                />
              </div>
              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-medium text-gray-700">
                  密码
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  placeholder="请输入密码"
                  autoComplete="current-password"
                  required
                />
              </div>
              {error && <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
              >
                {loading ? '登录中...' : '登录'}
              </button>
            </form>
            <div className="mt-6 text-xs leading-6 text-gray-400">
              登录后可访问评测集管理、评测任务、对比分析、图片视频代理预览等完整能力。
            </div>
          </div>
        </div>
      </div>
      <footer className="border-t border-white/10 bg-slate-950 px-4 py-4 text-center text-sm text-slate-400">
        Powered by 火山引擎行业解决方案团队 视觉智能专项小组
      </footer>
    </div>
  );
};
