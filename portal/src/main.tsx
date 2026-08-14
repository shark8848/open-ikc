import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

// 应用初始时应用持久化的显示样式（优先于首帧渲染，避免主题闪烁）
const savedTheme = localStorage.getItem('open-ikc-theme')
const root = document.documentElement
if (savedTheme && savedTheme !== 'dark') root.setAttribute('data-theme', savedTheme)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
