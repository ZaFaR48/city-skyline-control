async function loadDocs() {
  const response = await fetch("/openapi.json");
  const schema = await response.json();
  const list = document.getElementById("docsPaths");
  const pre = document.getElementById("docsSchema");
  pre.textContent = JSON.stringify(
    {
      openapi: schema.openapi,
      title: schema.info.title,
      version: schema.info.version,
    },
    null,
    2,
  );

  Object.entries(schema.paths).forEach(([path, methods]) => {
    Object.keys(methods).forEach((method) => {
      const item = document.createElement("div");
      item.className = "item";
      item.innerHTML = `<div class="item-title"><span>${method.toUpperCase()}</span><span>${path}</span></div>
        <p class="muted">${methods[method].summary || ""}</p>`;
      list.appendChild(item);
    });
  });
}

loadDocs().catch((error) => {
  document.getElementById("docsSchema").textContent = error.message;
});
