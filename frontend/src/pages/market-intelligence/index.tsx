import { useQuery } from 'react-query';
import { fetchData } from '../../utils/fetchData';
import { useLocation } from 'react-router-dom';
import { useEffect, useState, useMemo } from 'react';
import { parseQueryParams } from '../../utils/parseUrlParams';
import { Empty, Select, Button , Tooltip} from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { capitalizeFirstLetter } from '../../utils/helper';
import KOL from './kol';
import parse from 'html-react-parser';
import PatientStories from './patientStories';
import he from 'he';
import ApprovedDrug from './approvedDrug';
import ExportButton from '../../components/testExportButton';
import LoadingButton from '../../components/loading';
import IndicationsSummary from './indicationsSummary';
import { useChatStore } from 'chatbot-component';
import BotIcon from '../../assets/bot.svg?react';
import { preprocessIndicationsData } from '../../utils/llmUtils';
import Table from '../../components/testTable';
import ColumnSelector from './columnFilter';
const { Option } = Select;
const CustomHeader = (props) => {
    const { displayName } = props; // Receive disease name as a prop
    return (
		<div>

		<span>{displayName}</span>
        <Tooltip
            overlayClassName='custom-tooltip'
            color='#fff'
            title={`Powered by LLM`}
            overlayStyle={{ maxWidth: '350px' }}
        >
			
            
            <InfoCircleOutlined className=" text-base cursor-pointer ml-1 align-middle" />
        </Tooltip>
		</div>
    );
}
const extractEntriesFromIndicationPipeline = (indicationPipeline) => {
	const entries = [];
	Object.keys(indicationPipeline).forEach((disease) => {
		const diseaseEntries = indicationPipeline[disease];
		entries.push(...diseaseEntries);
	});
	return entries;
};

const CompetitiveLandscape = () => {
	const location = useLocation();
	// const [target, setTarget] = useState('');
	const [indications, setIndications] = useState([]);
	const [selectedDisease, setSelectedDisease] = useState(indications);
	const [selectedModality, setSelectedModality] = useState('All');
	// const [rowData, setRowData] = useState([]);
	const { register, invoke } = useChatStore();

	const columnDefs = [
		{
			field: 'NctIdTitleMapping',
			headerName: 'Trial summary',
			flex: 8,
			minWidth: 300,
			valueGetter: (params) => {
				if (params.data.NctIdTitleMapping) {
					return Object.entries(params.data.NctIdTitleMapping)
						.map(
							([key, value]) =>
								`<div><span className="font-semibold">${key}:</span> ${
									value ? value : 'No official title available'
								}</div>`
						)
						.join('\n\n');
				}
				return '';
			},
			cellStyle: { whiteSpace: 'pre-wrap' },
			filter: true,
			cellRenderer: (params) => {
				return parse(params.value);
			},
		},

		{
			field: 'Disease',
			cellRenderer: (params) => {
				return capitalizeFirstLetter(params.value);
			},
		},
		{
			field: 'Target',
		},
		{
			field: 'Source URLs',
			headerName: 'Trial id',
			flex: 2,
			cellRenderer: (params) =>
				params.value.map((value, index) => (
					<a key={index} className='mr-2' href={value} target='_blank'>
						{value.replace('https://clinicaltrials.gov/study/', '')}
						{params.value.length - 1 !== index ? ',' : ''}
					</a>
				)),
		},
		{
			field: 'OutcomeStatus',
			headerComponent: CustomHeader,
		headerComponentParams: {
			displayName: 'Trial outcome',
		},
			cellRenderer: (params) => {
				return capitalizeFirstLetter(params.value);
			},
		},
		{
			field: 'WhyStopped',
			headerName: 'Outcome reason',
			cellStyle: { whiteSpace: 'normal', lineHeight: '20px' },
			cellRenderer: (params) => {
				// Display both PMIDs and WhyStopped
				const pmidLinks = params.data.PMIDs.map((pmid, index) => (
					<a
						key={index}
						className='mr-2'
						href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`}
						target='_blank'
					>
						{pmid}
						{params.data.PMIDs.length - 1 !== index ? ',' : ''}
					</a>
				));
		
				// Show the WhyStopped value
				const whyStopped = he.decode(params.data.WhyStopped);
		
				return (
					<div>
						<div className='mb-2'>{`${params.data.PMIDs?.length>0 ? "PMID: " :""}`} {pmidLinks}</div>
						<div>{whyStopped}</div>
					</div>
				);
			},
			valueGetter: (params) => {
				// Return both PMIDs and WhyStopped as separate values
				return {
					pmids: params.data.PMIDs,
					whyStopped: params.data.WhyStopped
				};
			},
		},		
		{ field: 'Drug' },
		{ field: 'Phase' },
		{ field: 'Status' },
		{ field: 'Type', headerName: 'Modality' },
		{
			field: 'Sponsor',
			flex: 2,
			cellRenderer: (params) => {
				return he.decode(params.value);
			},
		},
		{
			field: 'Mechanism of Action',
			headerName: 'Mechanism of action',
			flex: 2,
		},
	];
	useEffect(() => {
		const queryParams = new URLSearchParams(location.search);
		const { indications } = parseQueryParams(queryParams);
		// setTarget(target);
		setIndications(indications);
	}, [location.search]);

	const payload = {
		diseases: indications,
	};

	const {
		data: indicationData,
		error: indicationError,
		isLoading,
		isFetching,
	} = useQuery(
		['marketIntelligenceIndications', payload],
		() => fetchData(payload, '/market-intelligence/indication-pipeline/'),
		{
			enabled: !!indications.length,
			refetchOnWindowFocus: false,
			staleTime: 5 * 60 * 1000,
			refetchOnMount: false,
		}
	);
	const [selectedColumns, setSelectedColumns] = useState([
		'Drug',
		'Disease',
		'Phase',
		'Status',
		'Type',
		'Sponsor',
		'Mechanism of Action',
		'Target',
		'OutcomeStatus',
		'WhyStopped',
		'Source URLs',
	]);

	useEffect(() => {
		setSelectedDisease(indications);
	}, [indications]);
	const visibleColumns = useMemo(() => {
		return columnDefs.filter((col) => selectedColumns.includes(col.field));
	}, [columnDefs, selectedColumns]);

	const handleColumnChange = (columns: string[]) => {
		setSelectedColumns(columns);
	};

	const handleDiseaseChange = (value: string[]) => {
		if (value.includes('All')) {
			// If "All" is selected, select all diseases but don't include "All" in display
			setSelectedDisease(indications);
		} else if (
			selectedDisease.length === indications.length &&
			value.length < indications.length
		) {
			// If coming from "all selected" state and deselecting, just use the new selection
			setSelectedDisease(value);
		} else {
			// Normal selection behavior
			setSelectedDisease(value);
		}
	};
	const handleModalityChange = (value) => setSelectedModality(value);
	const processedData = useMemo(() => {
		if (indicationData) {
			return extractEntriesFromIndicationPipeline(
				indicationData.indication_pipeline
			);
		}
		return [];
	}, [indicationData]);

	const filteredData = useMemo(() => {
		const diseaseFiltered = selectedDisease.includes('All')
			? processedData
			: processedData.filter((row) =>
					selectedDisease.some(
						(indication) =>
							indication.toLowerCase() === row.Disease.toLowerCase()
					)
			  );

		return selectedModality === 'All'
			? diseaseFiltered
			: diseaseFiltered.filter((item) => item.Type === selectedModality);
	}, [processedData, selectedDisease, selectedModality]);

	const showLoading = isLoading || isFetching;

	useEffect(() => {
		const llmData = preprocessIndicationsData(filteredData);
		register('pipeline_indications', {
			disease: selectedDisease.includes('All')
				? indications.map((indication) => indication.toLowerCase())
				: selectedDisease,
			modality:
				selectedModality == 'All'
					? [...new Set(processedData.map((item) => item.Type))]
					: selectedModality,
			data: llmData,
		});

		// return () => {
		// 	unregister('pipeline_indications');
		// };
	}, [filteredData]);

	const handleLLMCall = () => {
		invoke('pipeline_indications', { send: false });
	};

	return (
		<div className='mt-8'>
			<section id='approvedDrug'>
				<ApprovedDrug
					approvedDrugData={processedData}
					loading={isLoading}
					error={indicationError}
					indications={indications}
					isFetchingData={isFetching}
				/>
			</section>

			<section
				id='pipeline-by-indications'
				className='bg-gray-50 py-20 px-[5vw]'
			>
				<h1 className='text-3xl font-semibold '>Indication pipeline</h1>
				<p className='mt-2 font-medium'>
					The table offers a comprehensive overview of drug candidates,
					categorized by indication, development status, and mechanism of
					action, based on data from ongoing and completed clinical trials. It
					supports scientists in validating drug targets across modalities and
					indications.<br></br>
				</p>

				{showLoading ? (
					<LoadingButton />
				) : indicationError ? (
					// Error div with same height as AgGrid
					<div className='ag-theme-quartz mt-4 h-[80vh] max-h-[720px] flex items-center justify-center'>
						<Empty description={String(indicationError)} />
					</div>
				) : (
					<div>
						<div className='flex justify-between my-2'>
							<div className='flex gap-2'>
								<div>
									<span className='mt-1 mr-1'>Disease: </span>
									<Select
										style={{ width: 500 }}
										onChange={handleDiseaseChange}
										value={selectedDisease}
										mode='multiple'
										maxTagCount='responsive'

										// disabled={isLoading}
									>
										<Option key='All' value='All'>
											All
										</Option>
										{indications.map((indication) => (
											<Option key={indication} value={indication}>
												{indication}
											</Option>
										))}
									</Select>
								</div>
								<div>
									<span className='mt-1 mr-1'>Modality: </span>
									<Select
										style={{ width: 300 }}
										onChange={handleModalityChange}
										value={selectedModality}
										// disabled={isLoading}
									>
										<Option key='All' value='All'>
											All
										</Option>
										{[...new Set(processedData.map((item) => item.Type))].map(
											(type) => (
												<Option key={type} value={type}>
													{type}
												</Option>
											)
										)}
									</Select>
								</div>
							</div>
							<ExportButton
								indications={indications}
								fileName={'Indication Pipeline'}
								endpoint={'/market-intelligence/indication-pipeline/'}
							/>
						</div>
						<IndicationsSummary indicationData={filteredData} />
						<div className='space-x-4 flex justify-between items-center'>
							<div className='flex gap-2 items-center justify-center'>
								<h2 className='text-xl subHeading font-semibold '>
									List of trials by target
								</h2>
								<Button
									type='default' // This will give it a simple outline
									onClick={handleLLMCall}
									className='w-18 h-8 text-blue-800 text-sm flex items-center'
								>
									<BotIcon width={16} height={16} fill='#d50f67' />
									<span>Ask LLM</span>
								</Button>
							</div>

							<div className='flex flex-end'>
								<ColumnSelector
									allColumns={columnDefs}
									defaultSelectedColumns={selectedColumns}
									onChange={handleColumnChange}
								/>
							</div>
						</div>

						<div className='ag-theme-quartz mt-4 '>
							<Table
								columnDefs={visibleColumns}
								rowData={filteredData}
							/>
						</div>
					</div>
				)}
			</section>
			<section id='opinionLeaders' className='mt-12 min-h-[80vh] mb-10  px-[5vw]'>
				<KOL indications={indications} />
			</section>
			{/* <Patent target={target} indications={indications}/> */}
			<PatientStories indications={indications}/>
		</div>
	);
};

export default CompetitiveLandscape;
