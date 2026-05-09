const ajaxUrls = document.getElementById('articleFilterAjaxUrls');

const tagsAutocompleteUrl = ajaxUrls?.dataset.tagsUrl;
const authorsAutocompleteUrl = ajaxUrls?.dataset.authorsUrl;

$('#id_category, #id_ordering').select2({
  width: '100%',
  minimumResultsForSearch: 10,
});

if (authorsAutocompleteUrl) {
  $('#filterAuthorInput').select2({
    width: '100%',
    allowClear: true,
    placeholder: 'Any author',
    ajax: {
      url: authorsAutocompleteUrl,
      dataType: 'json',
      delay: 300,
      data: function (params) {
        return {
          q: params.term || '',
        };
      },
      processResults: function (data) {
        return data;
      },
    },
    minimumInputLength: 2,
  });
} else {
  $('#filterAuthorInput').select2({
    width: '100%',
    allowClear: true,
    placeholder: 'Any author',
    minimumResultsForSearch: 0,
  });
}

$('#filterTagsInput').select2({
  width: '100%',
  ajax: {
    url: tagsAutocompleteUrl,
    dataType: 'json',
    delay: 300,
    data: function (params) {
      return {
        q: params.term || '',
      };
    },
    processResults: function (data) {
      return data;
    },
  },
  minimumInputLength: 1,
});

$('#filterSubmit').click((e) => {
  e.preventDefault();

  const url = new URL(window.location.href.split('?')[0]);
  const params = new URLSearchParams();

  appendGetParameterFromInput(params, 'q', 'id_q');
  appendGetParameterFromInput(params, 'author', 'filterAuthorInput');
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
