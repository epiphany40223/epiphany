
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

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
import com.google.api.services.drive.Drive.Files;
import com.google.api.services.drive.DriveScopes;
import com.google.api.services.drive.model.File;
import com.google.api.services.drive.model.FileList;
import com.google.api.services.drive.model.User;
/**
 * @author fmcke
 *
 */
public class Quickstart {
    /** Application name. */
    private static final String APPLICATION_NAME =
       "Drive API Java Quickstart";

    /** Directory to store user credentials for this application. */
    private static final java.io.File DATA_STORE_DIR = new java.io.File(
     //   System.getProperty("user.home"), ".credentials/drive-java-quickstart");
    		System.getProperty("user.home"), "workspace3_1/FileMaintenanceG");

    /** Global instance of the {@link FileDataStoreFactory}. */
    private static FileDataStoreFactory DATA_STORE_FACTORY;

    /** Global instance of the JSON factory. */
    private static final JsonFactory JSON_FACTORY =
        JacksonFactory.getDefaultInstance();

    /** Global instance of the HTTP transport. */
    private static HttpTransport HTTP_TRANSPORT;

    /** Global instance of the scopes required by this quickstart.
     *
     * If modifying these scopes, delete your previously saved credentials
     * at ~/.credentials/drive-java-quickstart
     */
    private static final List<String> SCOPES =
        Arrays.asList(DriveScopes.DRIVE_METADATA_READONLY);

    static {
        try {
            HTTP_TRANSPORT = GoogleNetHttpTransport.newTrustedTransport();
            DATA_STORE_FACTORY = new FileDataStoreFactory(DATA_STORE_DIR);
        } catch (Throwable t) {
            t.printStackTrace();
            System.exit(1);
        }
    }

    /**
     * Creates an authorized Credential object.
     * @return an authorized Credential object.
     * @throws IOException
     */
    public static Credential authorize() throws IOException {
        // Load client secrets.
    	//String value = System.getProperty("user.home") + "\\workspace2_1\\FileMaintenance2"
       // 	    + "\\client_secret_0320.json";
    	String value = System.getProperty("user.home") + "\\workspace3_1\\FileMaintenanceG"
        	    + "\\client_secret_0320.json";
        InputStream in =
           Quickstart.class.getResourceAsStream("/client_secret_0320.json");
       //    Quickstart.class.getResourceAsStream(value);
   
        GoogleClientSecrets clientSecrets =
            GoogleClientSecrets.load(JSON_FACTORY, new InputStreamReader(in));

        // Build flow and trigger user authorization request.
        GoogleAuthorizationCodeFlow flow =
                new GoogleAuthorizationCodeFlow.Builder(
                        HTTP_TRANSPORT, JSON_FACTORY, clientSecrets, SCOPES)
                .setDataStoreFactory(DATA_STORE_FACTORY)
                .setAccessType("offline")
                .build();
        Credential credential = new AuthorizationCodeInstalledApp(
         //   flow, new LocalServerReceiver()).authorize("louisville0710@gmail");
        //		flow, new LocalServerReceiver()).authorize("louisville0101@gmail");
        flow, new LocalServerReceiver()).authorize("eccdrivebot@epiphanycatholicchurch.org");
        System.out.println(
                "Credentials saved to " + DATA_STORE_DIR.getAbsolutePath());
        return credential;
    }

    /**
     * Build and return an authorized Drive client service.
     * @return an authorized Drive client service
     * @throws IOException
     */
    public static Drive getDriveService() throws IOException {
        Credential credential = authorize();
        return new Drive.Builder(
                HTTP_TRANSPORT, JSON_FACTORY, credential)
                .setApplicationName(APPLICATION_NAME)
                .build();
    }

 public static void main(String[] args) throws IOException {
    	
    	String  topParentId = null;
    	
    	List    backupFolderList = new ArrayList();
    	Map     directoryMap = new HashMap();
    	Map     bottomUpDirectoryMap = new HashMap();
    	Map     fileMap = new HashMap();
    	File    newBackupFolderId = null;
    	
    	// Build a new authorized API client service.
        Drive service = getDriveService();
       
        List<File> fileList = createFileList (service); 
       
	    if (fileList.size() == 0) {
	        System.out.println("No files found.");
	        return ;
	    } 
	    
	    createMaps (fileList, directoryMap, bottomUpDirectoryMap, fileMap, backupFolderList);
	   
	    topParentId = getTopParentId (fileList, bottomUpDirectoryMap); 
	    System.out.printf("Top Parent:" + topParentId + "\n");
	        	
	    newBackupFolderId = createNewBackup(service, topParentId);
	    
	    processId (service, topParentId, directoryMap, fileMap, newBackupFolderId, backupFolderList);
	   
    }
    
    static private int processId (Drive service, String id, Map directoryMap, Map fileMap,  File backupFileId, List backupFolderList) {
    	
    	List fileList = (List) fileMap.get(id);
    	
    	int cnt = 0;
    	
    	if (fileList == null);
    	else {
	    	for (int i=0 ; i < fileList.size(); i++) {
	    		File file = (File) fileList.get(i);
	    		
	    		String label = cnt+")  file Name:" + file.getName() + ". Id:"+ file.getId() + ". MemeType:" +  file.getMimeType() + ". Users :";
		    	
		    	try {
		    	
		    		if (isOwnerMatch (file, "louisville0101@gmail.com", label));
		    		else if(isFileInBackupDirectory(file, backupFolderList));
		    		else  {
		    			System.out.printf("Make copy file: " + file.getName() + "\n");
		    			copyFile(service, file.getId(), file.getName(), backupFileId);
		    		}
		    	
		    	} catch (Exception ex) {
		    		int ii = 0;
		    		i++;
		    	}
		    	
		    	label = label + "\n";
		            	
		       	System.out.printf(label);
		            	
		    	cnt++;
	    	}
    	}
    	
    	fileList  = (List) directoryMap.get(id);
    	
    	if (fileList == null) ;
    	else {
	    	for (int i=0; i < fileList.size(); i++) {
	    		File file = (File) fileList.get(i);
	    		
	    		System.out.printf("process directory: " + file.getName() + "\n");
	    		processId (service, file.getId(), directoryMap, fileMap, backupFileId, backupFolderList);
	    	}
    	}
    	
    	return 0;
    }
 
    static private List<File> createFileList (Drive service) throws IOException { 

    	// File backupFile = null;
    	boolean  firstTime = true;
    	boolean  done = false;
    	FileList resultList = null;
    	List<File> fileList = new ArrayList();
    	String nextPageToken = null;
    	
    	while (!done) {
    
    		if (firstTime) {
    
    			// Print the names and IDs for up to 10 files.
    			resultList = service.files().list()
    				.setPageSize(1000)
    				.setFields("nextPageToken, files(id, name, owners, fileExtension, mimeType, parents)")
     				.execute();
    		} else {
    
    			resultList = service.files().list()
                    .setPageSize(1000)
                    .setPageToken(nextPageToken)
                    .setFields("nextPageToken, files(id, name, owners, fileExtension, mimeType, modifiedTime)")
                    .execute();
    		}
    	
    		firstTime = false;
    	
    		nextPageToken = resultList.getNextPageToken();
    	
    		List<File> files = resultList.getFiles();
    	
    		for (File file : files) {   			
    			fileList.add(file);
    		}
    	          
    		if (nextPageToken == null)
    			done = true;
    	}
    	
    	return fileList;
    }
    
    private static File copyFile(Drive service, String originFileId, String copyTitle, File backupFile) {
        
    	File copiedFile = new File();
        copiedFile.setName(copyTitle);
        
        List parents = new ArrayList();
        parents.add(backupFile.getId());
        
        copiedFile.setParents(parents);
      //  copiedFile.setTitle(copyTitle);
        
        try {
        	return service.files().copy(originFileId, copiedFile).execute();
        } catch (IOException e) {
        	System.out.println("An error occurred: " + e);
        }
        
        return null;
      }
    
    private static File createNewBackup(Drive service, String originFileId) {
  	    DateFormat df = new SimpleDateFormat("yyyyMMddHHmm");

  	    // Get the date today using Calendar object.
  	    Date today = Calendar.getInstance().getTime();        
  	    // Using DateFormat format method we can create a string 
  	    // representation of a date with the defined format.
  	    String reportDate = df.format(today);

        File fileMetadata = new File();
        fileMetadata.setName("Backup_" + reportDate);
        fileMetadata.setMimeType("application/vnd.google-apps.folder");
        
        List parents = new ArrayList();
        parents.add(originFileId);
        
        fileMetadata.setParents(parents); 
        
        try {
            return service.files().create(fileMetadata)
                    .setFields("id")
                    .execute();
          } catch (IOException e) {
            System.out.println("An error occurred: " + e);
        }
        
        return null;
 
    }
    
    static private void createMaps (List<File> fileList, Map directoryMap,Map bottomUpDirectoryMap, Map fileMap, List backupFolderList) {
    	
    	//   put directory list
    	for (int i=0; i < fileList.size(); i++) {
   		
    		File file = (File) fileList.get(i);
       	
    		String parent = file.getParents().get(0);
       		 
    		if (file.getMimeType().contains("folder")) {
    			List directoryList = (List) directoryMap.get(parent);
       	    	  
    			if (directoryList == null) {
    				directoryList = new ArrayList();
    				directoryMap.put(parent, directoryList);
    			}
       	    	  
    			directoryList.add(file);
   			
    			String id = (String) bottomUpDirectoryMap.get(file.getId());
 	    	  
    			if (id == null) 
    				bottomUpDirectoryMap.put(file.getId(),parent); 	
    			
    			if (file.getName().toLowerCase().contains("backup"))
    				backupFolderList.add(file.getId());

   
    		} else {
       	    	 	  
    			List fileMapList  = (List) fileMap.get(parent);
       	    	  
    			if (fileMapList == null ) {
    				fileMapList = new ArrayList();
    				fileMap.put(parent, fileMapList);
    			}
       	    	  
    			fileMapList.add(file);	    	  
    		}
    	}
   
    }
    
    static public String getTopParentId (List<File> fileList, Map bottomUpDirectoryMap) {
    	boolean topFound = false;
	
    	File file = (File) fileList.get(0);		
    	String topParent = file.getParents().get(0);
        		
    	while (!topFound) {
    		String temp = (String)bottomUpDirectoryMap.get(topParent);
        			
    		if (temp == null)
    			topFound = true;
    		else {
    			topParent = temp;
    		}
    	}
    	
    	return topParent;
    }
    
    static private boolean isOwnerMatch (File file, String matchOwner, String label) {
    
    	boolean   found = false;
	
    	for (User user : file.getOwners()) {
		
			if (user.getEmailAddress().toLowerCase().equals(matchOwner)) {
			   found = true;	
			}
		
			label = label + user.getEmailAddress() + ":" + user.getPermissionId() + ", ";	 
    	}
	
    	return found;
    }
    
    static private boolean isFileInBackupDirectory(File file, List backupFolderList) {
    	
    	List parentsList = file.getParents();
    	
    	for (int i = 0; i < parentsList.size(); i ++ ) {
    		
    		String parentId = (String) parentsList.get(i);
    		
    		for (int j=0; j < backupFolderList.size(); j++) {
    			if (parentId.equals(backupFolderList.get(j)))
    				return true;
    		}
    	}
    	
    	return false;
    }

    private  void useridStuff (Drive service, File file) {
	  
    	
    	// [{"displayName":"Fred McKernan","emailAddress":"louisville0710@gmail.com","kind":"drive#user","me":true,"permissionId":"15948924008377222193"}]
	    User userx = new User();
	    userx.setDisplayName("Fred McKernan");
	    userx.setEmailAddress("louisville0710@gmail.com");
	    userx.setKind("drive#user");
	    userx.setMe(true);
	    userx.setPermissionId("15948924008377222193");
	    
	    File filex = new File();
        filex.setOwners(file.getOwners());
        
        filex.getOwners().add(userx);

        // Rename the file.
   //    Files.Patch patchRequest = service.files().patch(file.getId(), file);
   //     patchRequest.setFields("owners");

       // File updatedFile = patchRequest.execute();
        		          
  //  	List<User> ownerList = file.getOwners();
    	
   // 	ownerList.add(userx);
    	
    //	file.setOwners(ownerList);
    
    }
}


