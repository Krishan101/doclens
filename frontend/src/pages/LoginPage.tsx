import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AuthForm from '../components/auth/AuthForm';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (email: string, password: string) => {
    await login(email, password);
    navigate('/');
  };

  return <AuthForm mode="login" onSubmit={handleLogin} switchMode={() => navigate('/signup')} />;
}
