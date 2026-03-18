import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Queue from './pages/Queue';
import { QueueProvider } from './contexts/QueueContext';

export default function App() {
  return (
    <BrowserRouter>
      <QueueProvider>
        <Layout>
          <Routes>
            <Route path="*" element={<Queue />} />
          </Routes>
        </Layout>
      </QueueProvider>
    </BrowserRouter>
  );
}
