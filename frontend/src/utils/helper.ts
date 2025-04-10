// Define a type for the input object
type InputObject = Record<string, any>;

// Define a type for the output array elements
type OutputArrayElement = {
	field: string;
	value: any;
};

// Function to convert object to array of objects
export function convertObjectToArray(
	inputObject: InputObject
): OutputArrayElement[] {
	if (!inputObject) return [];
	// Initialize an empty array to hold the result
	const resultArray: OutputArrayElement[] = [];

	// Iterate over each key-value pair in the input object
	for (const [key, value] of Object.entries(inputObject)) {
		// Push a new object into the result array with 'field' and 'value' keys
		resultArray.push({ field: key, value: value });
	}

	return resultArray; // Return the resulting array
}

export const capitalizeFirstLetter = (str) => 
	str ? str[0].toUpperCase() + str.slice(1).toLowerCase() : '';
export function convertToArray(data) {
	const result = [];
	Object.keys(data).forEach((disease) => {
	  data[disease]?.forEach((record) => {
		result.push({
		  ...record,
		  Disease:capitalizeFirstLetter(disease), // Add the disease key
		});
	  });
	});
	return result;
  }