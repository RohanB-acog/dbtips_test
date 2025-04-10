import React from 'react';
import { useQuery } from 'react-query';
import { CaretRightOutlined } from '@ant-design/icons';
import { Collapse, Tooltip, theme,Empty } from 'antd';
import type { CSSProperties } from 'react';
import type { CollapseProps } from 'antd';
import LoadingButton from '../../components/loading';
import { fetchData } from '../../utils/fetchData';
import { capitalizeFirstLetter } from '../../utils/helper';

const excludeSynonyms=["AIDP","Guillain-Barre syndrome, familial","polyneuropathy, inflammatory demyelinating, acute","GBS"]
const getItems: (panelStyle: CSSProperties, diseases: any[]) => CollapseProps['items'] = (panelStyle, diseases) => {
  return diseases?.map((disease, index) => ({
    key: index.toString(),
    label: capitalizeFirstLetter(disease.name),
    children: (
      <div className='flex gap-24'>
        <div className='flex-1'>
          <h2 className='text-lg font-medium'>Description</h2>
          <p className='text-base mt-1'>{disease.description}</p>
        </div>
        <div className='flex-1'>
          <h2 className='text-lg font-medium mb-2'>Synonyms</h2>
          <div className="flex flex-wrap gap-2">
            {disease?.synonyms?.map((synonym, synIndex) => (
              synonym?.terms?.map((term, termIndex) => (
               disease.name !== "Chronic inflammatory demyelinating polyneuropathy" && !excludeSynonyms.includes(term) &&
                <Tooltip title={synonym.relation} key={`${synIndex}-${termIndex}`} overlayClassName='custom-tooltip' color='#fff'>
                  
                  <div className="px-3 py-1 bg-blue-200 rounded-full text-sm text-gray-700 cursor-pointer">
                    {term}
                  </div>
                </Tooltip>
              ))
            ))}
          </div>
        </div>
      </div>
    ),
    style: panelStyle,
  }));
};

const Description: React.FC<{  indications: string[] }> = ({  indications }) => {
  const { token } = theme.useToken();
console.log("indications", indications);
  const panelStyle: React.CSSProperties = {
    marginBottom: 5,
    background: "whitesmoke",
    borderRadius: token.borderRadiusLG,
    border: 'none',
    fontFamily: 'Poppins',
    padding: '0.3rem 0',
  };
  
  const payload = {
    diseases: indications,
  };

  const { data: diseaseDetailsData, error: diseaseDetailsError, isLoading: diseaseDetailLoading } = useQuery(
    ['diseaseDetails', payload],
    () => fetchData(payload, '/disease-profile/details/'),
    {
      enabled:  !!indications.length,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
      refetchOnMount: false,
    
    }
  );
  return (
    <section>
      <article className='mt-8 px-[5vw]' id='disease-description'>
        <h1 className='text-3xl font-semibold mb-3'>Description</h1>
        {diseaseDetailLoading ? (
          <LoadingButton />
        ) : diseaseDetailsError ? (
          <div className=' h-[50vh] max-h-[280px] flex items-center justify-center'>
            <Empty description={` ${diseaseDetailsError}`} />
          </div >
        ) : diseaseDetailsData?.data?.diseases?.length ? (
          <Collapse
            bordered={false}
            defaultActiveKey={['0']}
            expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
            style={{ background: token.colorBgContainer }}
            items={getItems(panelStyle, diseaseDetailsData.data.diseases)}
          />
        ) : (
          <div>
            <Empty description='No data available' />
          </div>
        )}
      </article>
    </section>
  );
}

export default Description;