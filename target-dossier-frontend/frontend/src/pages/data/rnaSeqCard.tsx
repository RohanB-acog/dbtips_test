import { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery } from 'react-query';
import { Select, Pagination, Empty, Button } from 'antd';
import LoadingButton from '../../components/loading';
import { fetchData } from '../../utils/fetchData';
import { useLocation } from 'react-router-dom';
import { parseQueryParams } from '../../utils/parseUrlParams';
import Card from './card';
import { useChatStore } from 'chatbot-component';
import BotIcon from '../../assets/bot.svg?react';
import { preprocessRnaseqData } from '../../utils/llmUtils';

import ExportButton from '../../components/testExportButton';

const { Option } = Select;
function convertToArray(data) {
	const result = [];
	Object.keys(data).forEach((disease) => {
		data[disease].forEach((record) => {
			result.push({
				...record,
				Disease: disease, // Add the disease key
			});
		});
	});
	return result;
}
// Move constants outside component to prevent recreation
const PAGE_SIZE = 5;

const RnaSeqCard = () => {
	const [filters, setFilters] = useState({
		disease: 'All',
		organism: 'Human',
		page: 1,
		studyType: 'scRNA',
		platformName: 'All',
	});
	const [uniquePlatformNames, setUniquePlatformNames] = useState([]);
	const location = useLocation();
	const [indications, setIndications] = useState([]);
	const [dataArray, setDataArray] = useState([]);

	const { register, invoke } = useChatStore();

	const queryPayload = useMemo(
		() => ({
			diseases: indications,
		}),
		[indications]
	);

	useEffect(() => {
		const queryParams = new URLSearchParams(location.search);
		const { indications: newIndications } = parseQueryParams(queryParams);

		setIndications(newIndications);
	}, [location]);

	const {
		data: rnaSeqData,
		error,
		isLoading,
	} = useQuery(
		['rnaSeqData', queryPayload],
		() => fetchData(queryPayload, '/evidence/rna-sequence/'),
		{
			enabled: Boolean(indications.length),
			refetchOnWindowFocus: false,
			staleTime: 1000 * 60 * 5, // 5 minutes in milliseconds
			refetchOnMount: false,
		}
	);

	useEffect(() => {
		if (!rnaSeqData) return;
		const updatedData = convertToArray(rnaSeqData);
		setDataArray(updatedData);
	}, [rnaSeqData]);

	useEffect(() => {
		if (dataArray.length === 0) return;
		const uniquePlatformNames =
			dataArray.length > 0
				? Array.from(
						new Set(
							(filters.disease === 'All'
								? dataArray
								: dataArray.filter(
										(data) =>
											data.Disease.toLowerCase() ===
											filters.disease.toLowerCase()
								  )
							).flatMap((data) => data.PlatformNames) // Flatten arrays of PlatformNames
						)
				  )
				: [];

		setUniquePlatformNames(uniquePlatformNames);
	}, [dataArray, filters, rnaSeqData]);

	const {
		filteredData,
		paginatedData,
		totalItems,
		totalStudies,
		humanStudiesCount,
		singleRnaCount,
		bulkRnaCount,
		MicroarrayCount,
	} = useMemo(() => {
		const availableDiseases = Object.keys(rnaSeqData || {});
		const selectedDiseaseData =
			filters.disease === 'All'
				? dataArray
				: dataArray.filter(
						(data) => data.Disease === filters.disease.toLowerCase()
				  );

		const filtered = selectedDiseaseData.filter((data) => {
			// Check if the organism filter is "All" or matches the organism
			const organismMatches =
				filters.organism === 'All' || data.Organism[0] === filters.organism;
			const platformNameMatches =
				filters.platformName === 'All' ||
				data.PlatformNames.includes(filters.platformName);
			// Check if the study type matches the selected filter
			const studyTypeMatches =
				filters.studyType === 'All' || data.StudyType == filters.studyType;

			// Include data only if it matches the organism filter and the study type filter
			return organismMatches && studyTypeMatches && platformNameMatches;
		});

		const totalStudies = selectedDiseaseData.length;
		// Count human studies in the selectedDiseaseData
		const humanStudiesCount = selectedDiseaseData.filter(
			(data) => data.Organism[0] === 'Human'
		).length;
		const singleRnaCount = selectedDiseaseData.filter(
			(data) => data.StudyType === 'scRNA'
		).length;
		const bulkRnaCount = selectedDiseaseData.filter(
			(data) => data.StudyType === 'bulkRNA'
		).length;
		const MicroarrayCount = selectedDiseaseData.filter(
			(data) => data.StudyType === 'Microarray'
		).length;

		return {
			diseases: availableDiseases,
			filteredData: filtered,
			paginatedData: filtered.slice(
				(filters.page - 1) * PAGE_SIZE,
				filters.page * PAGE_SIZE
			),
			totalItems: filtered.length,
			totalStudies,
			humanStudiesCount,
			singleRnaCount,
			bulkRnaCount,
			MicroarrayCount,
		};
	}, [rnaSeqData, filters, dataArray]);

	const handleFilterChange = useCallback((key, value) => {
		setFilters((prev) => ({
			...prev,
			[key]: value,
			page: key !== 'page' ? 1 : value,
		}));
	}, []);

	useEffect(() => {
		if (filteredData && filters?.disease) {
			const llmData = preprocessRnaseqData(filteredData);
			console.log(llmData);
			register('rnaseq', {
				disease:
					filters.disease === 'All'
						? indications.map((indication) => indication.toLowerCase())
						: filters.disease,
				organism: filters.organism,
				platform_name: filters.platformName,
				study_type:
					filters.studyType == 'All'
						? ['scRNA', 'bulkRNA', 'Microarray', 'Not Known']
						: filters.studyType,
				data: llmData,
			});
		}
	}, [filteredData, filters]);

	const handleLLMCall = () => {
		invoke('rnaseq', { send: false });
	};

	return (
		<article id='rnaSeq' className='  mt-5 px-[5vw]'>
			<div className='flex space-x-5 items-center'>
				<h1 className='text-3xl font-semibold'>RNA-seq Datasets</h1>
				<div className='space-x-2'>
					<Button
						type='default' // This will give it a simple outline
						onClick={handleLLMCall}
						className='w-18 h-8 text-blue-800 text-sm flex items-center'
					>
						<BotIcon width={16} height={16} fill='#d50f67' />
						<span>Ask LLM</span>
					</Button>
				</div>
			</div>
			<p className=' font-medium mt-2 mb-2'>
				Single-cell studies provide more granular insights compared to bulk
				studies.
			</p>
			{isLoading && <LoadingButton />}
			{error && !rnaSeqData && <Empty description='Error' />}
			{/* {!isLoading && !error  && !rnaSeqData && (
        <Empty description="No data available" />
      )} */}
			{filters.disease && !isLoading && dataArray.length > 0 && (
				<section className='mb-10'>
					<div className='flex justify-between my-2'>
						<div className='flex gap-2'>
							<div>
								<span>Disease: </span>
								<Select
									placeholder='Select a disease'
									value={filters.disease}
									onChange={(value) => handleFilterChange('disease', value)}
									style={{ width: 300 }}
								>
									<Option key='all' value='All'>
										All
									</Option>
									{indications.map((disease) => (
										<Option key={disease} value={disease}>
											{disease}
										</Option>
									))}
								</Select>
							</div>

							<div>
								<span>Organism: </span>
								<Select
									className='w-32'
									placeholder='Select an organism'
									value={filters.organism}
									onChange={(value) => handleFilterChange('organism', value)}
								>
									<Option value='Human'>Human</Option>
									<Option value='All'>All</Option>
								</Select>
							</div>
							<div>
								<span>Platform name: </span>
								{uniquePlatformNames && dataArray && (
									<Select
										style={{ width: 200 }}
										placeholder='Select an organism'
										value={filters.platformName}
										showSearch
										onChange={(value) =>
											handleFilterChange('platformName', value)
										}
									>
										<Option key='all' value='All'>
											All
										</Option>

										{uniquePlatformNames.map((platformName) => (
											<Option key={platformName} value={platformName}>
												{platformName}
											</Option>
										))}
									</Select>
								)}
							</div>
							<div>
								<span>Study type: </span>
								<Select
									style={{ width: 150 }}
									placeholder='Select an Study Type'
									value={filters.studyType}
									onChange={(value) => handleFilterChange('studyType', value)}
								>
									<Option value='All'>All</Option>
									<Option value='scRNA'>scRNA</Option>
									<Option value='bulkRNA'>bulkRNA</Option>
									<Option value='Microarray'>Microarray</Option>
									<Option value='Not Known'>Not Known</Option>
								</Select>
							</div>
						</div>
						{
							<ExportButton
								indications={indications}
								endpoint={'/evidence/rna-sequence/'}
								fileName={'RNASeqDataset'}
							/>
						}
					</div>
					<span className='font-bold'>Summary: </span>
					<span>
						{' '}
						<span className='text-sky-800'>{totalStudies} </span>studies,{' '}
						<span className='text-sky-800'>{humanStudiesCount}</span> in{' '}
						<span className='italic'>Human,</span>{' '}
						<span className='text-sky-800'>{singleRnaCount}</span> single cell,{' '}
						<span className='text-sky-800'>{bulkRnaCount}</span> bulk RNA
						{' and '}
						<span className='text-sky-800'>{MicroarrayCount}</span> microarray
						studies.
					</span>
					<div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
						{paginatedData.map((diseaseData, index) => (
							<Card
								key={`${filters.disease}-${index}-${filters.page}`}
								diseaseData={diseaseData}
							/>
						))}
					</div>
					{paginatedData.length == 0 && (
						<div className='flex items-center justify-center h-[50vh]'>
							<Empty description='No data available' />
						</div>
					)}

					{totalItems > PAGE_SIZE && (
						<Pagination
							current={filters.page}
							pageSize={PAGE_SIZE}
							total={totalItems}
							onChange={(page) => handleFilterChange('page', page)}
							showSizeChanger={false}
							className='mt-5'
						/>
					)}
				</section>
			)}
		</article>
	);
};

export default RnaSeqCard;
