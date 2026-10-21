import { createApp } from "vue"

import App from "./Root.vue"
import router from "./router"
import "./styles.css"

createApp(App).use(router).mount("#app")
