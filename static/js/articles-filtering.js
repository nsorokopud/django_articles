$('#id_author, #id_category, #id_ordering').select2({
  width: '100%',
  minimumResultsForSearch: 10,
});
$('#filterTagsInput').select2({ width: '100%' });

$('#filterSubmit').click((e) => {
  e.preventDefault();

  const url = new URL(window.location.href.split('?')[0]);
  const params = new URLSearchParams();

  appendGetParameterFromInput(params, 'q', 'id_q');
  appendGetParameterFromInput(params, 'author', 'id_author');
  appendGetParameterFromInput(params, 'date_after', 'id_date_0');
  appendGetParameterFromInput(params, 'date_before', 'id_date_1');
  appendGetParameterFromInput(params, 'category', 'id_category');

  const tags = $('#filterTagsInput').val() || [];
  for (const tag of tags) {
    params.append('tags', tag);
  }

  appendGetParameterFromInput(params, 'ordering', 'id_ordering');

  url.search = params.toString();
  window.location.href = url.toString();
});

function appendGetParameterFromInput(params, name, inputId) {
  const value = document.getElementById(inputId)?.value;
  if (value) {
    params.set(name, value);
  }
}
