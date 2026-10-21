import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import MoneyDisplay from "./MoneyDisplay.vue"

describe("MoneyDisplay", () => {
  it("renders CNY values with two decimal places", () => {
    const wrapper = mount(MoneyDisplay, { props: { value: "60000.00" } })

    expect(wrapper.text()).toContain("60,000.00")
    expect(wrapper.text()).toContain("¥")
  })
})
