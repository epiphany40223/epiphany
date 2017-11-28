import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.google.api.client.auth.oauth2.Credential;
import com.google.api.client.extensions.java6.auth.oauth2.AuthorizationCodeInstalledApp;
import com.google.api.client.extensions.jetty.auth.oauth2.LocalServerReceiver;
import com.google.api.client.googleapis.auth.oauth2.GoogleAuthorizationCodeFlow;
import com.google.api.client.googleapis.auth.oauth2.GoogleClientSecrets;
import com.google.api.client.googleapis.javanet.GoogleNetHttpTransport;
import com.google.api.client.http.HttpTransport;
import com.google.api.client.json.JsonFactory;
import com.google.api.client.json.jackson2.JacksonFactory;
import com.google.api.client.util.store.FileDataStoreFactory;
import com.google.api.services.drive.Drive;
import com.google.api.services.drive.DriveScopes;
import com.google.api.services.drive.model.File;
import com.google.api.services.drive.model.FileList;
import com.google.api.services.drive.model.User;

// rename  file non-owned    to copy
//   if doc   then add this has been copied
// copy renamed to name
/**
 * @author fmcke
 *
 */
public class Quickstart {
	
	private static Logger logger  = Logger.getLogger("Quickstart");
	
    /** Application name. */
    private static final String APPLICATION_NAME =
       "Drive API Java Quickstart";

    /** Directory to store user credentials for this application. */
  //x  private static final java.io.File DATA_STORE_DIR = new java.io.File(
     //   System.getProperty("user.home"), ".credentials/drive-java-quickstart");
    //x		System.getProperty("user.home"), "workspace3_3/FileMaintenanceG");

    /** Global instance of the {@link FileDataStoreFactory}. */
 //x   private static FileDataStoreFactory DATA_STORE_FACTORY;

    /** Global instance of the JSON factory. */
    private static final JsonFactory JSON_FACTORY =
        JacksonFactory.getDefaultInstance();

    /** Global instance of the HTTP transport. */
//    private static HttpTransport HTTP_TRANSPORT;

    /** Global instance of the scopes required by this quickstart.
     *
     * If modifying these scopes, delete your previously saved credentials
     * at ~/.credentials/drive-java-quickstart
     */
    private static final List<String> SCOPES =
     //   Arrays.asList(DriveScopes.DRIVE_METADATA_READONLY);
    	Arrays.asList(DriveScopes.DRIVE);

//x    static {
//x        try {
      //x      HTTP_TRANSPORT = GoogleNetHttpTransport.newTrustedTransport();
      //x      DATA_STORE_FACTORY = new FileDataStoreFactory(DATA_STORE_DIR);
 //x       } catch (Throwable t) {
 //x           t.printStackTrace();
 //x           System.exit(1);
 //x       }
 //x   }

    /**
     * Creates an authorized Credential object.
     * @return an authorized Credential object.
     * @throws IOException
     */
    public static Credential authorize(String authorizationId, String clientSecretJson, HttpTransport httpTransport, FileDataStoreFactory dataStoreFactory) throws IOException {
        // Load client secrets.

    	logger.info("start credentials. authorizationId <"+ authorizationId +">. clientSecretJson <"+ clientSecretJson+">");

    	//String value = System.getProperty("user.home") + "\\workspace3_3\\FileMaintenanceG"
        //	    + "\\client_secret_0812.json";
        InputStream in =
        		Quickstart.class.getResourceAsStream(clientSecretJson);
          		// Quickstart.class.getResourceAsStream("/client_secret_0812c.json");
   
        logger.info("get client secrets");
        
        GoogleClientSecrets clientSecrets =
            GoogleClientSecrets.load(JSON_FACTORY, new InputStreamReader(in));

        logger.info("get code flow");
        
        // Build flow and trigger user authorization request.
        GoogleAuthorizationCodeFlow flow =
                new GoogleAuthorizationCodeFlow.Builder(
  //                      HTTP_TRANSPORT, JSON_FACTORY, clientSecrets, SCOPES)
                		  httpTransport, JSON_FACTORY, clientSecrets, SCOPES)
            //    .setDataStoreFactory(DATA_STORE_FACTORY)
                .setDataStoreFactory(dataStoreFactory)
            //    .setAccessType("offline")
                .build();
        
        logger.info("create credentials");
        
        Credential credential = new AuthorizationCodeInstalledApp(
              //flow, new LocalServerReceiver()).authorize("eccdrivebot@epiphanycatholicchurch.org");
        		flow, new LocalServerReceiver()).authorize(authorizationId);
        
  //x      System.out.println(
  // x             "Credentials saved to " + DATA_STORE_DIR.getAbsolutePath());
        
        return credential;
    }

    /**
     * Build and return an authorized Drive client service.
     * @return an authorized Drive client service
     * @throws IOException
     */
    public static Drive getDriveService(String authorizationId, String clientSecretJson, HttpTransport httpTransport, FileDataStoreFactory dataStoreFactory) throws IOException {
       
    	logger.info("start getDriveService. authorizationId <"+ authorizationId +">. clientSecretJson <"+ clientSecretJson+">");

    	Credential credential = authorize(authorizationId, clientSecretJson, httpTransport, dataStoreFactory);
    
    	return new Drive.Builder(
  //              HTTP_TRANSPORT, JSON_FACTORY, credential)
    			 httpTransport, JSON_FACTORY, credential)
                .setApplicationName(APPLICATION_NAME)
                .build();
    }
    

    public static void main(String[] args) throws IOException {
    	
    	//String  topParentId = null;
    	
    	//List    backupFolderList = new ArrayList();
    //	Map     directoryMap = new HashMap();
    	//Map     bottomUpDirectoryMap = new HashMap();
    //	Map     fileMap = new HashMap();
    //	File    newBackupFolderId = null;
    	String  authorizationId = "";
    	String  clientSecretJson = "";
    	String   wildcard = "********~";
    	HttpTransport httpTransport = null;
		FileDataStoreFactory dataStoreFactory = null;
		java.io.File dataStoreDir = null;
		String dataStoreDirIn = null;
    	 
    	logger.info("Start quickstart");
           
    	   
        for (int i =0 ;  i < args.length; i++) {
        	
        	if (args[i].toLowerCase().equals("-a")) {
        		i++;
        		authorizationId = args[i];
        	} else if (args[i].toLowerCase().equals("-c")) {
        		i++;
        		clientSecretJson = args[i];
        	} else if (args[i].toLowerCase().equals("-d")) {
             		i++;
             		dataStoreDirIn = args[i];
        	} else if (args[i].toLowerCase().equals("-h")) {
         		i++;
         		logger.info("Quickstart -a [authorizationId] -c [clientSecretJJson] -d [dataStoreDirIn] -w [wildcard]");
         		System.exit(1);
        	} else if (args[i].toLowerCase().equals("-w")) {
        		i++;
        		wildcard = args[i];
        	}
        }
    	
        dataStoreDir = new java.io.File(dataStoreDirIn);
	
        try {
    		httpTransport = GoogleNetHttpTransport.newTrustedTransport();
    		dataStoreFactory = new FileDataStoreFactory(dataStoreDir);
    	} catch (Throwable t) {
    	     t.printStackTrace();
    	     System.exit(1);
    	}
        
        int ptr = wildcard.indexOf("~");
        
        if (ptr < 0);
        else if (ptr == 0)
        	wildcard = "";
        else
        	wildcard = wildcard.substring(0, ptr);

        logger.info("wildcard <"+wildcard+">. authorizationId <"+ authorizationId +">. clientSecretJson <"+ clientSecretJson+">");

    	// Build a new authorized API client service.
        Drive service = getDriveService(authorizationId, clientSecretJson, httpTransport, dataStoreFactory);
      
        logger.info("Drive service successfull created");
        
        List<File> fileList = createFileList (service); 
       
        logger.info("fileList created length <"+ fileList.size() +">");
        
	    if (fileList.size() == 0) {
	    	logger.info("No files pulled back");
	        System.out.println("No files found.");
	        return ;
	    } 
	    
	    logger.info("Call process id");
	    
	    processId (service, fileList, authorizationId, wildcard);
	   
    }

    static private List<File> createFileList (Drive service) throws IOException { 

    	boolean  firstTime = true;
    	boolean  done = false;
    	FileList resultList = null;
    	List<File> fileList = new ArrayList<File>();
    	String nextPageToken = null;
    	
    	logger.info("Start createFileList");
    	 
    	while (!done) {
    
    		if (firstTime) {
    
    			// Print the names and IDs for up to 10 files.
    			resultList = service.files().list()
    				.setPageSize(1000)
    				.setFields("nextPageToken, files(id, description, name, owners, fileExtension, mimeType, parents, shared)")
     				.execute();
    		} else {
    
    			resultList = service.files().list()
                    .setPageSize(1000)
                    .setPageToken(nextPageToken)
                    .setFields("nextPageToken, files(id,description, name, owners, fileExtension, mimeType, modifiedTime)")
                    .execute();
    		}
    	
    		firstTime = false;
    	
    		nextPageToken = resultList.getNextPageToken();
    	
    		List<File> files = resultList.getFiles();
    	
    		for (File file : files) {   	
    			
    			if (file.getShared()) {
    				logger.info("file  <"+ file.getName() +"> is shared   - bypass");
    				continue;
    			}
    			
    			fileList.add(file);
    		}
    	          
    		if (nextPageToken == null)
    			done = true;
    	}
    	
    	logger.info("End createFileList");
    	
    	return fileList;
    }


    static private int processId (Drive service, List<File> fileList, String owner, String wildcard) {
   
    	logger.info("Start processId");
    	
    	for (int i=0 ; i < fileList.size(); i++) {
    		File file = (File) fileList.get(i);
 
    		if (wildcard.isEmpty());
    		else if (file.getName().startsWith(wildcard));
    		else {
    			logger.info("file <"+ file.getName() +"> does not match wildcard <"+wildcard+">");
    			continue;
    		}
    		
    		if (file.getMimeType().contains("folder"))
    			logger.info("file <"+ file.getName() +"> is folder");
    		else if (file.getName().toLowerCase().startsWith("backupxx_"))
    			logger.info("file <"+ file.getName() +"> is backup name");
    		else if (isOwnerMatch (file, owner))
    			logger.info("file <"+ file.getName() +"> is owned by <"+ owner +">");	
    		else {
    		
    			try {
		    		
    				String currentFileName = file.getName();
    				
    				File renameFile = new File();
    				renameFile.setName("backupxx_" + file.getName());
		    			
    				//List parents = new ArrayList();	        
		    		//renameFile.setParents(parents);
		    		        
		    		service.files().update(file.getId(), renameFile).execute();
		    	   
		    		logger.info("file <"+ currentFileName +"> renamed to  <"+renameFile.getName() +">");
		    		
		    		System.out.printf("Make copy file: " + file.getName() + "\n");
		    		copyFile(service, file.getId(), currentFileName);
		    		
		    		logger.info("file <"+ renameFile.getName() +"> copied to <"+currentFileName +">");
		    		
		    		System.out.printf("file <"+ currentFileName+"> is renamed");
	            	
		    	
		    	} catch (Exception ex) {
		    		int ii = 0;
		    		i++;
		    	}
		    	
		    	//label = label + "\n";
		            	
		       
		    	//cnt++;
	    	}
    	}
    	
    	logger.info("End createFileList");
    	
    	return 0;
    }
 
  
	static private boolean isOwnerMatch (File file, String matchOwner) {

		boolean   found = false;

		for (User user : file.getOwners()) {
	
			if (user.getEmailAddress().toLowerCase().equals(matchOwner)) {
				found = true;	
			}
	
			//label = label + user.getEmailAddress() + ":" + user.getPermissionId() + ", ";	 
		}

		return found;
	}
	
    private static File copyFile(Drive service, String originFileId, String fileName) {
        
    	File copiedFile = new File();
        copiedFile.setName(fileName);
        
        try {
        	return service.files().copy(originFileId, copiedFile).execute();
        } catch (IOException e) {
        	System.out.println("An error occurred: " + e);
        }
        
        return null;
     }
    
}


