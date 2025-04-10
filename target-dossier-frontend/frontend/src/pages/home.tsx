import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Form, Select, Input, ConfigProvider } from 'antd';
import type { FormProps } from 'antd';
import { capitalizeFirstLetter } from '../utils/helper';
import gifImage from '../assets/Cover_page_TD.png'; // Update path as needed
import { useLocation } from 'react-router-dom';
import { parseQueryParams } from '../utils/parseUrlParams';
import { SearchOutlined } from '@ant-design/icons';
import { fetchData } from '../utils/fetchData';

type FieldType = {
  target?: string;
  indications?: string[];
};

const { Option } = Select;

const Home = ({ setAppState }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [options, setOptions] = useState([]);

  const [target, setTarget] = useState('');
  const [indications, setIndications] = useState([]);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // const options = [
  //   { id: '1', name: 'Prurigo nodularis' },
  //   { id: '2', name: 'Alopecia areata' },
  //   { id: '3', name: 'Asthma' },
  //   { id: '4', name: 'Hidradenitis suppurativa' },
  //   { id: '5', name: 'Chronic idiopathic urticaria' },
  // ];
  const fetchSuggestions = async (query) => {
    setLoading(true);
    const payload = { queryString: query };
    try {
      const response = await fetchData(payload, '/search');
      const suggestions = response.data.search.hits;
      setOptions(suggestions);
    } catch (error) {
      console.error('Error fetching suggestions:', error);
    }
    setLoading(false);
  };
  useEffect(() => {
		const queryParams = new URLSearchParams(location.search);
		const { target, indications } = parseQueryParams(queryParams);

      const parsedIndications = indications ?indications.map((indication) => capitalizeFirstLetter(indication)):[];
      setIndications(parsedIndications);
   
		setTarget(target);
		// setIndications(indications);
    form.setFieldsValue({ target:target, indications : parsedIndications });
	}, [location, Form]);
 
  


  const handleSearch = (value) => {
    if (value) {
      fetchSuggestions(value);
    } else {
      setOptions([]);
    }
  };

  

  const onFinish: FormProps<FieldType>['onFinish'] = (values) => {
    const encodedIndications = values.indications
      .map((indication) => `"${capitalizeFirstLetter(indication)}"`)
      .join(',');
    setAppState((prev) => ({
      ...prev,
      target: values.target,
      indications: values.indications,
    }));
    navigate(`/target-biology?target=${values.target}&indications=${encodeURIComponent(encodedIndications)}`);
  };
const handleTargetChange = (e) => {
    setTarget(e.target.value);
  }
  
  const isButtonEnabled = target || indications.length > 0;
  return (
    <>
    <div className="bg-gradient-to-b h-[86vh] from-indigo-50 to-white hero">
      <div className="max-w-[96rem] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center mb-8">
          <h3 className="text-4xl text-gray-900 font-bold mb-4">
            Disease Biomarker & Target Insights Platform & Services (DBTIPS™)
          </h3>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Your guide to transforming complex data into actionable insights and empower target validation, and advancing precision-driven research and innovation.</p>        </div>
        <section className="grid grid-cols-1 md:grid-cols-2 gap-12  ">
        <div>
            <img
              src={gifImage}
              alt="Informative GIF"
              className="w-full h-[60vh] object-contain rounded-lg"
              loading='lazy'
            />
          </div>
          <div className='flex items-center'>

          
          <div className='w-full'>

          <Form
                form={form}
                layout="vertical"
                labelWrap={true}
                className="max-w-2xl mx-auto mb-16"
                style={{ width: '100%' }}
                onFinish={onFinish}
                
          
              >
                <Form.Item
                  label="Target:"
                  name="target"
                  rules={[{ message: "Please input your target!" }]}

                >
                  <Input
                    placeholder="Please enter a target!"
                    prefix={<SearchOutlined className="text-2xl" />}
                    className="w-full pl-4 pr-4 py-4 rounded-xl border-2 border-gray-100 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all text-lg"
                    onChange={handleTargetChange}
                  />
                </Form.Item>
                <ConfigProvider
                  theme={{
                    components: {
                      Select: {
                        multipleItemHeightLG: 38,
                      },
                    },
                    token: {
                      controlHeight: 44,
                      paddingSM: 20,
                    },
                  }}
                >
                  <Form.Item name="indications" label="Indications:">
                 
                    <Select
                      mode="multiple"
                      showSearch={true}
                      onSearch={handleSearch}                      size="large"
                      placeholder="Please select an indication"
                      className=" rounded-xl border-2 border-gray-100 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-all text-lg "
                      allowClear
                      loading={loading}
                      notFoundContent={null}

                    >
                      {options.map((option) => (
                        <Option key={option.id} value={capitalizeFirstLetter(option.name)}>
                          {capitalizeFirstLetter(option.name)}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </ConfigProvider>

                <Form.Item>
                  <Button
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-6 px-6 rounded-xl font-semibold text-lg transition-all duration-200 flex items-center justify-center gap-2 hover:gap-3"
                    htmlType="submit"
                    disabled={!isButtonEnabled}
                  >
                    Search         

                  </Button>
                </Form.Item>
              </Form>
          </div>
          </div>
        </section>

      </div>

    </div>
    
    </>
  );
};

export default Home;