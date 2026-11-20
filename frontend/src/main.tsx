import { render } from '@solidjs/web'
import { App } from './shell/App'
import './app.css'

const root = document.getElementById('root')
if (!root) throw new Error('Missing root element')
render(() => <App />, root)
