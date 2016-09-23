#include "FreeImage.h"
#include <algorithm>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <algorithm>

struct Deleter
{
	void operator()(FIBITMAP* ptr) const
	{
		FreeImage_Unload(ptr);
	}
};

using bitmap_ptr = std::unique_ptr<FIBITMAP, Deleter>;

/** Generic image loader
@param lpszPathName Pointer to the full file name
@param flag Optional load flag constant
@return Returns the loaded dib if successful, returns NULL otherwise
*/
bitmap_ptr GenericLoader(const std::string& lpszPathName, int flag = 0) {
	auto fif = FIF_UNKNOWN;

	// check if file path is not empty
	if (lpszPathName.empty())
		return nullptr;

	// check the file signature and deduce its format
	// (the second argument is currently not used by FreeImage)
	fif = FreeImage_GetFileType(lpszPathName.c_str(), 0);
	if (fif == FIF_UNKNOWN) {
		// no signature ?
		// try to guess the file format from the file extension
		fif = FreeImage_GetFIFFromFilename(lpszPathName.c_str());
	}
	// check that the plugin has reading capabilities ...
	if ((fif != FIF_UNKNOWN) && FreeImage_FIFSupportsReading(fif)) {
		// ok, let's load the file
		bitmap_ptr dib(FreeImage_Load(fif, lpszPathName.c_str(), flag));
		// unless a bad file format, we are done !
		return dib;
	}
	return nullptr;
}

/** Generic image writer
@param dib Pointer to the dib to be saved
@param lpszPathName Pointer to the full file name
@param flag Optional save flag constant
@return Returns true if successful, returns false otherwise
*/
bool GenericWriter(const bitmap_ptr& dib, const std::string& lpszPathName, int flag) {
	auto fif = FIF_UNKNOWN;
	auto bSuccess = FALSE;
	// check if file path is not empty
	if (lpszPathName.empty())
		return false;
	if (dib) {
		// try to guess the file format from the file extension
		fif = FreeImage_GetFIFFromFilename(lpszPathName.c_str());
		if (fif != FIF_UNKNOWN) {
			// check that the plugin has sufficient writing and export capabilities ...
			if (FreeImage_FIFSupportsWriting(fif) && FreeImage_FIFSupportsExportType(fif, FreeImage_GetImageType(dib.get()))) {
				// ok, we can save the file
				bSuccess = FreeImage_Save(fif, dib.get(), lpszPathName.c_str(), flag);
				// unless an abnormal bug, we are done !
			}
			else {
				std::cout << "Can't save file" << lpszPathName << std::endl;
			}
		}
    else {
      std::cerr << "Can't determine output file type" << std::endl;
    }
	}
	return (bSuccess == TRUE);
}

// ----------------------------------------------------------

/**
FreeImage error handler
@param fif Format / Plugin responsible for the error
@param message Error message
*/
void FreeImageErrorHandler(FREE_IMAGE_FORMAT fif, const char *message) {
	std::cerr << "\n*** ";
	if (fif != FIF_UNKNOWN) {
		std::cerr << FreeImage_GetFormatFromFIF(fif) << " Format\n";
	}
	std::cerr << message << " ***\n";
}

// ----------------------------------------------------------

class TaskCollector {

protected:
	std::vector<std::string> chunks;
	std::vector<std::string> alphaChunks;
	unsigned int width;
	unsigned int height;

public:
	TaskCollector() = default;
	TaskCollector(const TaskCollector&) = delete;
	TaskCollector(TaskCollector &&other)
	{
		chunks = std::move(other.chunks);
		alphaChunks = std::move(other.alphaChunks);
	}
	~TaskCollector() = default;

	bool addImgFile(std::string pathName)  {
		if (pathName.empty())
			return false;
		chunks.emplace_back(std::move(pathName));
		return true;
	};

	bool addAlphaFile(std::string pathName) {
		if (pathName.empty())
			return false;
		alphaChunks.emplace_back(std::move(pathName));
		return true;
	};

	virtual bitmap_ptr finalize(bool showProgress = false) = 0;

	bool finalizeAndSave(std::string outputPath) {
		if (outputPath.empty())
			return false;
		std::cout << "finalize & save " << outputPath << std::endl;
		auto img = finalize();
    return GenericWriter(img, outputPath, EXR_FLOAT);
	};
	void set_width(unsigned int w) {
		width = w;
	};
	void set_height(unsigned int h) {
		height = h;
	};

};

class AddTaskCollector : public TaskCollector {

public:
	bitmap_ptr finalize(bool showProgress = false) {
		if (chunks.empty()) {
			return nullptr;
		}
		if (showProgress) {
			std::cout << "Adding all accepted chunks to the final image\n";
		}

		const auto it = chunks.begin();
		
		bitmap_ptr firstChunk = GenericLoader(*it);
		
		const auto type = FreeImage_GetImageType(firstChunk.get());
		
		bitmap_ptr finalImage(FreeImage_Copy(firstChunk.get(), 0, height, width, 0));

		auto RGBChunkWorker = [=, &finalImage](const std::string& el)
		{
			bitmap_ptr chunk = GenericLoader(el);
			auto chunkHeight = FreeImage_GetHeight(chunk.get());
			for (unsigned int y = 0; y < chunkHeight; ++y) {
				auto srcbits = reinterpret_cast<FIRGBF *>(FreeImage_GetScanLine(chunk.get(), y));
				auto dstbits = reinterpret_cast<FIRGBF *>(FreeImage_GetScanLine(finalImage.get(), y));

				for (unsigned int x = 0; x < this->width; ++x) {
					dstbits[x].red += srcbits[x].red;
					dstbits[x].blue += srcbits[x].blue;
					dstbits[x].green += srcbits[x].green;
				}
			}
		};

		auto RGBAChunkWorker = [=, &finalImage](const std::string& el)
		{
			bitmap_ptr chunk = GenericLoader(el);
			auto chunkHeight = FreeImage_GetHeight(chunk.get());
			for (unsigned int y = 0; y < chunkHeight; ++y) {
				const auto srcbits = reinterpret_cast<FIRGBAF *>(FreeImage_GetScanLine(chunk.get(), y));
				auto dstbits = reinterpret_cast<FIRGBAF *>(FreeImage_GetScanLine(finalImage.get(), y));

				for (unsigned int x = 0; x < this->width; ++x) {
					dstbits[x].red += srcbits[x].red;
					dstbits[x].blue += srcbits[x].blue;
					dstbits[x].green += srcbits[x].green;
					dstbits[x].alpha += srcbits[x].alpha;
				}
			}
		};

		auto alphaChunksWorker = [this, &finalImage](const std::string& el)
		{
			bitmap_ptr chunk = GenericLoader(el);
			auto chunkHeight = FreeImage_GetHeight(chunk.get());
			for (unsigned int y = 0; y < chunkHeight; ++y) {
				const auto srcbits = reinterpret_cast<FIRGBAF *>(FreeImage_GetScanLine(chunk.get(), y));
				auto dstbits = reinterpret_cast<FIRGBAF *>(FreeImage_GetScanLine(finalImage.get(), y));

				for (unsigned int x = 0; x < this->width; ++x) {
					dstbits[x].alpha += srcbits[x].red + srcbits[x].blue + srcbits[x].green;
				}
			}
		};

		if (type == FIT_RGBF)
			std::for_each(std::next(chunks.begin()), chunks.end(), RGBChunkWorker);
		else if (type == FIT_RGBAF)
			std::for_each(std::next(chunks.begin()), chunks.end(), RGBAChunkWorker);
		std::for_each(alphaChunks.begin(), alphaChunks.end(), alphaChunksWorker);

		return finalImage;
	}
};

class PasteTaskCollector : public TaskCollector {

public:
	bitmap_ptr finalize(bool showProgress = true) {
		if (chunks.empty()) {
			return nullptr;
		}
		if (showProgress) {
			std::cout << "Adding all accepted chunks to the final image\n";
		}
		
		const auto it = chunks.begin();
		bitmap_ptr firstChunk = GenericLoader(*it);
		
		auto currentHeight = 0;

		const auto type = FreeImage_GetImageType(firstChunk.get());
		
		const auto bpp = FreeImage_GetBPP(firstChunk.get());
		
		bitmap_ptr finalImage(FreeImage_AllocateT(type, width, height, bpp));

		auto RGBChunkWorker = [=, &finalImage, &currentHeight](const std::string& el)
		{
			bitmap_ptr chunk = GenericLoader(el);
			auto chunkHeight = FreeImage_GetHeight(chunk.get());
			auto chunk_img = FreeImage_Copy(chunk.get(), 0, 0, this->width, chunkHeight);
			if (chunk_img) {
				FreeImage_Paste(finalImage.get(), chunk_img, 0, currentHeight, 256);
			}
			currentHeight += chunkHeight;
		};

		std::for_each(chunks.begin(), chunks.end(), RGBChunkWorker);
		return finalImage;
	}
};

int main(int argc, char *argv[]) {
	// call this ONLY when linking with FreeImage as a static library
#ifdef FREEIMAGE_LIB
	FreeImage_Initialise();
#endif // FREEIMAGE_LIB

	// initialize your own FreeImage error handler
	FreeImage_SetOutputMessage(FreeImageErrorHandler);

	// print version & copyright infos
	std::cout << "FreeImage version : " << FreeImage_GetVersion() << "\n"
	          << FreeImage_GetCopyrightMessage() << std::endl;

	if (argc < 4) {
		std::cerr << "Usage: taskcollector.exe <type> <width> <height> <outputfile> <inputfile1> [<input file2> ...]\n";
		return -1;
	}

	std::unique_ptr<TaskCollector> taskCollector;

	std::string command{argv[1]};
	if (command == "add") {
		taskCollector = std::make_unique<AddTaskCollector>();
	}
	else if (command == "paste") {
		taskCollector = std::make_unique<PasteTaskCollector>();
	}
	else {
		std::cerr << "Unknown command '" << command << "'. Allowed: 'add', 'paste'.\n";
		return -1;
	}
	taskCollector->set_width(std::stoi(argv[2]));
	taskCollector->set_height(std::stoi(argv[3]));
	//to be sure the ordering is proper
	std::sort(argv + 5, argv + argc);

	for (int i = 5; i < argc; ++i) {
		if (std::string(argv[i]).find("Alpha") == std::string::npos) {
			if (!taskCollector->addImgFile(argv[i])) {
				std::cerr << "Can't add file: " << argv[i] << "\n";
			}
		}
		else {
			if (!taskCollector->addAlphaFile(argv[i])) {
				std::cerr << "Can't add file: " << argv[i] << "\n";
			}
		}
	}

	std::string name{argv[4]};
	auto it = name.find_last_of('.');
	name = ( (it == std::string::npos) ? (name + ".exr") : (name.substr(0, it) + ".Alpha.exr") );

  bool saved = taskCollector->finalizeAndSave(argv[4]);
	// call this ONLY when linking with FreeImage as a static library
#ifdef FREEIMAGE_LIB
	FreeImage_DeInitialise();
#endif // FREEIMAGE_LIB
  if (saved)
    return 0;
  else
    return 1;
}
