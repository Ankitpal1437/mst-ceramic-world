import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ProductSearch from './pages/ProductSearch';
import AdminPanel from './pages/AdminPanel';
import Layout from './components/Layout';

function App() {
  const [user, setUser] = React.useState(null);

  return (
    <Router>
      <Layout user={user} setUser={setUser}>
        <Routes>
          <Route path="/login" element={<Login setUser={setUser} />} />
          <Route path="/dashboard" element={user ? <Dashboard user={user} /> : <Navigate to="/login" />} />
          <Route path="/search" element={user ? <ProductSearch /> : <Navigate to="/login" />} />
          <Route path="/admin" element={user?.role === 'admin' ? <AdminPanel /> : <Navigate to="/dashboard" />} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
