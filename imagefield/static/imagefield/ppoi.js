;(() => {
  function movePoint(point, img, x, y) {
    point.style.left = `${img.clientWidth * x}px`
    point.style.top = `${img.clientHeight * y}px`
  }

  function ppoiFieldFor(field) {
    if (!field.dataset.ppoiId) return null
    return document.querySelector(`#${field.dataset.ppoiId}`)
  }

  function initPoint(field) {
    const ppoiField = ppoiFieldFor(field)
    if (!ppoiField) return

    const img = field.querySelector("img.imagefield-preview-image")
    let point = field.querySelector(".imagefield-point")
    if (!point) {
      point = document.createElement("div")
      point.className = "imagefield-point opaque"
      img.parentNode.appendChild(point)

      setTimeout(() => {
        point.className = "imagefield-point"
      }, 1000)
    }

    const matches = ppoiField.value.match(/^([.0-9]+)x([.0-9]+)$/)
    if (matches) {
      movePoint(
        point,
        img,
        Number.parseFloat(matches[1]),
        Number.parseFloat(matches[2]),
      )
    } else {
      movePoint(point, img, 0.5, 0.5)
    }
  }

  function previewSelectedFile(input) {
    const field = input.closest(".imagefield")
    if (!field) return

    const preview = field.querySelector(".imagefield-preview")
    const img = preview.querySelector("img.imagefield-preview-image")
    if (!("originalSrc" in img.dataset)) {
      img.dataset.originalSrc = preview.hidden ? "" : img.src
    }
    if (img.src.startsWith("blob:")) URL.revokeObjectURL(img.src)

    const file = input.files?.[0]
    if (file?.type.startsWith("image/")) {
      const ppoiField = ppoiFieldFor(field)
      if (ppoiField) ppoiField.value = "0.5x0.5"
      img.src = URL.createObjectURL(file)
      preview.hidden = false
    } else if (img.dataset.originalSrc) {
      img.src = img.dataset.originalSrc
      preview.hidden = false
    } else {
      img.src = "data:,"
      preview.hidden = true
    }
  }

  function centerpointWidget() {
    for (const field of document.querySelectorAll(
      ".imagefield[data-ppoi-id]",
    )) {
      if (!field.querySelector(".imagefield-preview").hidden) initPoint(field)
    }

    document.body.addEventListener("click", (e) => {
      if (e.target?.matches?.("img.imagefield-preview-image")) {
        const field = e.target.closest(".imagefield[data-ppoi-id]")
        const ppoiField = field && ppoiFieldFor(field)
        if (!ppoiField) return

        const point = field.querySelector(".imagefield-point")
        if (!point) return
        const img = e.target
        const x = e.offsetX / img.clientWidth
        const y = e.offsetY / img.clientHeight
        ppoiField.value = `${x.toFixed(3)}x${y.toFixed(3)}`
        movePoint(point, img, x, y)
      }
    })

    document.body.addEventListener("change", (e) => {
      if (e.target?.matches?.(".imagefield input[type=file]")) {
        previewSelectedFile(e.target)
      }
    })

    // Position the point once a newly selected image has been loaded
    document.body.addEventListener(
      "load",
      (e) => {
        if (
          e.target?.matches?.("img.imagefield-preview-image") &&
          !e.target.closest(".imagefield-preview").hidden
        ) {
          initPoint(e.target.closest(".imagefield"))
        }
      },
      true,
    )
  }

  window.addEventListener("load", centerpointWidget)
})()
