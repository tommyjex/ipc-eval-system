import { createBrowserRouter, RouterProvider, Link, Outlet } from 'react-router-dom';
import { DatasetListPage } from './pages/datasets/DatasetListPage';
import { DatasetCreatePage } from './pages/datasets/DatasetCreatePage';
import { DatasetDetailPage } from './pages/datasets/DatasetDetailPage';

function Layout() {
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/" className="flex items-center">
                <img 
                  src="https://xujianhua-utils.tos-cn-beijing.volces.com/AI-IPC/IPC%20logo.jpg" 
                  alt="Logo" 
                  className="h-10 w-auto mr-4"
                />
                <span className="text-xl font-bold text-gray-900">评测平台</span>
              </Link>
              <div className="ml-10 flex items-center space-x-4">
                <Link to="/datasets" className="text-gray-600 hover:text-gray-900 px-3 py-2">
                  评测集管理
                </Link>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

function HomePage() {
  return (
    <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            欢迎使用摄像头场景大模型评测平台
          </h1>
          <p className="text-lg text-gray-600 mb-8">
            数据集管理 | 标注 | 模型选择 | 评测 | 打分 | 报告生成
          </p>
          <Link
            to="/datasets"
            className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
          >
            开始使用
          </Link>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900">评测集管理</h3>
              <p className="mt-2 text-sm text-gray-500">
                创建和管理视频、图片类型的评测集，支持本地上传和TOS导入
              </p>
            </div>
          </div>
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900">数据标注</h3>
              <p className="mt-2 text-sm text-gray-500">
                支持人工标注和大模型自动标注，批量标注提高效率
              </p>
            </div>
          </div>
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900">模型评测</h3>
              <p className="mt-2 text-sm text-gray-500">
                选择大模型进行评测，生成评测报告和评分
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const router = createBrowserRouter(
  [
    {
      path: '/',
      element: <Layout />,
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
      ],
    },
  ],
  {
    future: {
      v7_startTransition: true,
    },
  }
);

function App() {
  return <RouterProvider router={router} />;
}

export default App;
