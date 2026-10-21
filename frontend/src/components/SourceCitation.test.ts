import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import SourceCitation from "./SourceCitation.vue"

describe("SourceCitation", () => {
  it("renders the real source name, page, snippet and score", () => {
    const wrapper = mount(SourceCitation, {
      props: {
        hit: {
          document_id: "doc-1",
          filename: "采购制度.pdf",
          chunk_id: "chunk-1",
          page_number: 2,
          snippet: "超过一万元需要财务审批。",
          score: 0.8234,
        },
      },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    })

    expect(wrapper.text()).toContain("采购制度.pdf")
    expect(wrapper.text()).toContain("第 2 页")
    expect(wrapper.text()).toContain("82.3%")
    expect(wrapper.text()).toContain("超过一万元需要财务审批。")
  })

  it("does not invent a page number when none is available", () => {
    const wrapper = mount(SourceCitation, {
      props: {
        hit: {
          document_id: "doc-1",
          filename: "制度.txt",
          chunk_id: "chunk-1",
          page_number: null,
          snippet: "制度片段",
          score: 0.5,
        },
      },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    })

    expect(wrapper.text()).toContain("页码不可用")
  })
})
