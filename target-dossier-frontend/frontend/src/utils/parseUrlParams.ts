export const parseQueryParams = (queryParams) => {
	const targetParam = queryParams.get('target');
	const indicationsParam = queryParams.get('indications');

	let parsedIndications: string[] = [];

	// Parse indications as an array of values within double quotes
	if (indicationsParam) {
		const regex = /"([^"]+)"/g;
		let match;

		while ((match = regex.exec(indicationsParam)) !== null) {
			parsedIndications.push(match[1]); // match[1] contains the value between quotes
		}
	}

	return { target: targetParam, indications: parsedIndications };
};
