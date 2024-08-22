$('#id_author, #id_category, #id_ordering').select2({
    width: '100%',
    minimumResultsForSearch: 10,
});
$('#filterTagsInput').select2({ width: '100%' });

$('#filterSubmit').click((e) => {
    e.preventDefault();

    const getParameters = {};
    appendGetParameterFromInput('q', 'id_q', getParameters);
    appendGetParameterFromInput('author', 'id_author', getParameters);
    appendGetParameterFromInput('date_after', 'id_date_0', getParameters);
    appendGetParameterFromInput('date_before', 'id_date_1', getParameters);
    appendGetParameterFromInput('category', 'id_category', getParameters);

    const tagsInput = document.getElementById('filterTagsInput');
    if (getSelectValues(tagsInput).length > 0) {
        getParameters.tags = getSelectValues(tagsInput).join('&tags=');
    }

    appendGetParameterFromInput('ordering', 'id_ordering', getParameters);

    try {
        const url = new URL(window.location.href.split('?')[0]);
        url.search = decodeURIComponent(new URLSearchParams(getParameters));
        window.location.href = url;
    } catch (e) {
        console.error(e);
    }
});

function appendGetParameterFromInput(name, inputId, getParameters) {
    let input = document.getElementById(inputId);
    if (input.value != '') {
        getParameters[name] = input.value;
    }
}

function getSelectValues(select) {
    let result = [];
    let options = select && select.options;

    for (let i = 0; i < options.length; i++) {
        let opt = options[i];

        if (opt.selected) {
            result.push(opt.value || opt.text);
        }
    }
    return result;
}
