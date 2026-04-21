import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api';

const LOGIN_HERO_IMAGE = 'https://xujianhua-utils.tos-cn-beijing.volces.com/AI-IPC/frontend-assets/login_hero_v3.png';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
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
    <div
      className="min-h-screen bg-slate-950"
      style={{
        backgroundImage: `linear-gradient(135deg, rgba(15,23,42,0.72) 0%, rgba(30,41,59,0.5) 42%, rgba(15,23,42,0.2) 100%), url(${LOGIN_HERO_IMAGE})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="min-h-[calc(100vh-52px)] px-4 py-10 sm:px-8 lg:px-12">
        <div className="mx-auto flex min-h-[calc(100vh-132px)] max-w-7xl items-center justify-between gap-8">
          <div className="hidden max-w-2xl self-end pb-28 lg:-ml-10 lg:block">
            <div className="rounded-3xl bg-slate-950/32 px-8 py-7 backdrop-blur-[2px]">
            <div className="mb-4 inline-flex rounded-full border border-white/15 bg-white/10 px-4 py-1 text-sm text-blue-100 backdrop-blur">
              Visual Intelligence Evaluation
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-white drop-shadow-[0_2px_10px_rgba(15,23,42,0.35)]">
              视觉智能评测平台
            </h1>
            <p className="mt-5 max-w-xl text-base leading-8 text-slate-100">
              面向视觉智能与家庭安防场景，统一支持评测集管理、任务评测、智能评分与多模型对比分析，帮助团队快速验证模型效果与方案价值。
            </p>
            </div>
          </div>

          <div className="w-full max-w-md rounded-3xl border border-gray-200 bg-white p-8 shadow-2xl ring-1 ring-black/5 sm:mr-6 sm:p-10">
            <div className="mb-8">
              <div className="mb-3 text-sm font-medium uppercase tracking-[0.2em] text-blue-600">Admin Login</div>
              <h2 className="text-3xl font-bold text-gray-900">欢迎登录</h2>
              <p className="mt-3 text-sm leading-6 text-gray-700">
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
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-xl border border-gray-200 px-4 py-3 pr-14 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    placeholder="请输入密码"
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute inset-y-0 right-0 flex items-center px-4 text-sm text-gray-500 hover:text-gray-700"
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                  >
                    {showPassword ? '隐藏' : '显示'}
                  </button>
                </div>
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
            <div className="mt-6 text-xs leading-6 text-gray-600">
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
