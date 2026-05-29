import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AuthForm from '../components/auth/AuthForm';

export default function SignupPage() {
  const navigate = useNavigate();
  const { signup } = useAuth();

  const handleSignup = async (email: string, password: string) => {
    await signup(email, password);
    navigate('/');
  };

  return <AuthForm mode="signup" onSubmit={handleSignup} switchMode={() => navigate('/login')} />;
}
