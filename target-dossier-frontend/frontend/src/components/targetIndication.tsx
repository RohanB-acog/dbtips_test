import { useLocation } from "react-router-dom";

const SelectionBanner = ({ target, indications }) => {
  const location = useLocation();

  // Do not render the banner if the location is "/"
  if (location.pathname === "/") {
    return null;
  }
  return (
    <div className="sticky top-[60px] border-t bg-white shadow  py-4 z-50 flex items-center justify-between">
      <div className="flex flex-wrap items-center gap-2 px-[5vw]">
        <span className="font-semibold text-lg text-gray-800">Target:</span>
        <span className="text-base ">{target}</span>
        <span className="font-semibold text-lg text-gray-800">Indications:</span>
        <div className="flex flex-wrap gap-1">
          {indications.map((indication, index) => (
            <span
              key={index}
              className="text-base  py-1 rounded-lg"
            >
              {indication}
              {index !== indications.length - 1 && " | "}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SelectionBanner;
