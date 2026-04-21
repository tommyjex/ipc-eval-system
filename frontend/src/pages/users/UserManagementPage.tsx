import React, { useEffect, useMemo, useState } from 'react';
import { userApi } from '../../api';
import type { User, UserCreateRequest, UserRole, UserStatus, UserUpdateRequest } from '../../api';

type CreateFormState = {
  username: string;
  password: string;
  nickname: string;
  role: UserRole;
  status: UserStatus;
};

type EditFormState = {
  nickname: string;
  role: UserRole;
  status: UserStatus;
};

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  user: '普通用户',
};

const STATUS_LABELS: Record<UserStatus, string> = {
  active: '启用',
  disabled: '禁用',
};

const getRoleBadgeClass = (role: UserRole) =>
  role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800';

const getStatusBadgeClass = (status: UserStatus) =>
  status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700';

const INITIAL_CREATE_FORM: CreateFormState = {
  username: '',
  password: '',
  nickname: '',
  role: 'user',
  status: 'active',
};

export const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [keywordInput, setKeywordInput] = useState('');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<20 | 50 | 100>(20);
  const [total, setTotal] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [resettingUser, setResettingUser] = useState<User | null>(null);
  const [createForm, setCreateForm] = useState<CreateFormState>(INITIAL_CREATE_FORM);
  const [editForm, setEditForm] = useState<EditFormState>({ nickname: '', role: 'user', status: 'active' });
  const [resetPassword, setResetPassword] = useState('');

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await userApi.list({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
      });
      setUsers(response.items);
      setTotal(response.total);
    } catch (error) {
      alert(`获取用户列表失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, pageSize, keyword]);

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setCreateForm(INITIAL_CREATE_FORM);
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setEditForm({
      nickname: user.nickname || '',
      role: user.role,
      status: user.status,
    });
  };

  const closeEditModal = () => {
    setEditingUser(null);
    setEditForm({ nickname: '', role: 'user', status: 'active' });
  };

  const openResetPasswordModal = (user: User) => {
    setResettingUser(user);
    setResetPassword('');
  };

  const closeResetPasswordModal = () => {
    setResettingUser(null);
    setResetPassword('');
  };

  const handleCreateUser = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const payload: UserCreateRequest = {
        username: createForm.username.trim(),
        password: createForm.password,
        nickname: createForm.nickname.trim() || undefined,
        role: createForm.role,
        status: createForm.status,
      };
      await userApi.create(payload);
      closeCreateModal();
      await fetchUsers();
    } catch (error) {
      alert(`创建用户失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateUser = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingUser) return;
    setSubmitting(true);
    try {
      const payload: UserUpdateRequest = {
        nickname: editForm.nickname.trim() || undefined,
        role: editForm.role,
        status: editForm.status,
      };
      await userApi.update(editingUser.id, payload);
      closeEditModal();
      await fetchUsers();
    } catch (error) {
      alert(`更新用户失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!resettingUser) return;
    setSubmitting(true);
    try {
      await userApi.resetPassword(resettingUser.id, { password: resetPassword });
      closeResetPasswordModal();
      alert('密码已重置');
    } catch (error) {
      alert(`重置密码失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (!window.confirm(`确定删除用户“${user.username}”吗？`)) return;
    try {
      await userApi.delete(user.id);
      await fetchUsers();
    } catch (error) {
      alert(`删除用户失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">用户管理</h1>
          <p className="mt-2 text-sm text-gray-600">管理员可创建、编辑、重置密码和删除普通用户账号。</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          创建用户
        </button>
      </div>

      <div className="mb-6 rounded-lg bg-white p-4 shadow">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            type="text"
            placeholder="搜索用户名或昵称..."
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            className="flex-1 rounded border px-3 py-2"
          />
          <button
            onClick={() => {
              setPage(1);
              setKeyword(keywordInput.trim());
            }}
            className="rounded bg-gray-100 px-4 py-2 hover:bg-gray-200"
          >
            搜索
          </button>
          <button
            onClick={() => {
              setKeywordInput('');
              setKeyword('');
              setPage(1);
            }}
            className="rounded border px-4 py-2 text-gray-600 hover:bg-gray-50"
          >
            重置
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-10 text-center">加载中...</div>
      ) : users.length === 0 ? (
        <div className="rounded-lg bg-white py-10 text-center text-gray-500 shadow">暂无用户</div>
      ) : (
        <div className="overflow-hidden rounded-lg bg-white shadow">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">用户名</th>
                <th className="px-4 py-3 text-left">昵称</th>
                <th className="px-4 py-3 text-left">角色</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">最近登录</th>
                <th className="px-4 py-3 text-left">创建时间</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{user.username}</td>
                  <td className="px-4 py-3 text-gray-600">{user.nickname || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded px-2 py-1 text-xs ${getRoleBadgeClass(user.role)}`}>
                      {ROLE_LABELS[user.role]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded px-2 py-1 text-xs ${getStatusBadgeClass(user.status)}`}>
                      {STATUS_LABELS[user.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {new Date(user.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-3 text-sm">
                      <button onClick={() => openEditModal(user)} className="text-blue-600 hover:text-blue-800">
                        编辑
                      </button>
                      <button onClick={() => openResetPasswordModal(user)} className="text-amber-600 hover:text-amber-800">
                        重置密码
                      </button>
                      <button onClick={() => handleDeleteUser(user)} className="text-red-600 hover:text-red-800">
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span>共 {total} 条</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value) as 20 | 50 | 100);
              setPage(1);
            }}
            className="rounded border px-2 py-1"
          >
            <option value={20}>20条/页</option>
            <option value={50}>50条/页</option>
            <option value={100}>100条/页</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page === 1}
            className="rounded border px-3 py-1 disabled:opacity-50"
          >
            上一页
          </button>
          <span className="px-3 py-1 text-sm">
            第 {page} / {totalPages} 页
          </span>
          <button
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            disabled={page === totalPages}
            className="rounded border px-3 py-1 disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">创建用户</h2>
              <button onClick={closeCreateModal} className="text-gray-400 hover:text-gray-600">
                关闭
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">用户名</label>
                <input
                  type="text"
                  value={createForm.username}
                  onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">初始密码</label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">昵称</label>
                <input
                  type="text"
                  value={createForm.nickname}
                  onChange={(e) => setCreateForm({ ...createForm, nickname: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700">角色</label>
                  <select
                    value={createForm.role}
                    onChange={(e) => setCreateForm({ ...createForm, role: e.target.value as UserRole })}
                    className="w-full rounded border px-3 py-2"
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700">状态</label>
                  <select
                    value={createForm.status}
                    onChange={(e) => setCreateForm({ ...createForm, status: e.target.value as UserStatus })}
                    className="w-full rounded border px-3 py-2"
                  >
                    <option value="active">启用</option>
                    <option value="disabled">禁用</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={closeCreateModal} className="rounded border px-4 py-2 text-gray-600">
                  取消
                </button>
                <button type="submit" disabled={submitting} className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300">
                  {submitting ? '提交中...' : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">编辑用户</h2>
              <button onClick={closeEditModal} className="text-gray-400 hover:text-gray-600">
                关闭
              </button>
            </div>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">用户名</label>
                <input type="text" value={editingUser.username} className="w-full rounded border bg-gray-50 px-3 py-2 text-gray-500" disabled />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">昵称</label>
                <input
                  type="text"
                  value={editForm.nickname}
                  onChange={(e) => setEditForm({ ...editForm, nickname: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700">角色</label>
                  <select
                    value={editForm.role}
                    onChange={(e) => setEditForm({ ...editForm, role: e.target.value as UserRole })}
                    className="w-full rounded border px-3 py-2"
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700">状态</label>
                  <select
                    value={editForm.status}
                    onChange={(e) => setEditForm({ ...editForm, status: e.target.value as UserStatus })}
                    className="w-full rounded border px-3 py-2"
                  >
                    <option value="active">启用</option>
                    <option value="disabled">禁用</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={closeEditModal} className="rounded border px-4 py-2 text-gray-600">
                  取消
                </button>
                <button type="submit" disabled={submitting} className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300">
                  {submitting ? '保存中...' : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {resettingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">重置密码</h2>
              <button onClick={closeResetPasswordModal} className="text-gray-400 hover:text-gray-600">
                关闭
              </button>
            </div>
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
                当前用户：<span className="font-medium text-gray-900">{resettingUser.username}</span>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">新密码</label>
                <input
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  className="w-full rounded border px-3 py-2"
                  required
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={closeResetPasswordModal} className="rounded border px-4 py-2 text-gray-600">
                  取消
                </button>
                <button type="submit" disabled={submitting} className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300">
                  {submitting ? '提交中...' : '确认重置'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
